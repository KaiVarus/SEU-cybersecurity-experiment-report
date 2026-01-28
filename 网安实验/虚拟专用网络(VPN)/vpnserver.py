#!/usr/bin/env python3

import os
import sys
import socket
import select
import struct
import fcntl
import subprocess
import threading
from threading import Lock
import time
import ssl
import ipaddress

# Constants
PORT = 4433
TUN_NAME = b"tun0"
BUFFER_SIZE = 2000
MAX_CLIENTS = 10
CERT_FILE = "server-cert.pem"
KEY_FILE = "server-key.pem"
CA_FILE = "ca-cert.pem"
DHCP_POOL_START = "192.168.53.100"
DHCP_POOL_END = "192.168.53.200"
SUBNET_MASK = "255.255.255.0"
LEASE_TIME = 3600  # 1 hour in seconds

# Global variables
clients = {}  # key: virtual_ip, value: client_info
client_lock = Lock()
server_socket = None
tun_fd = None
dhcp_pool = []  # List of available IP addresses


class ClientInfo:
    def __init__(self, ssl_socket, client_address, virtual_ip):
        self.ssl_socket = ssl_socket
        self.client_address = client_address
        self.virtual_ip = virtual_ip
        self.last_active = time.time()
        self.thread = None
        self.running = True
        self.lease_expiry = time.time() + LEASE_TIME


def init_dhcp_pool():
    """Initialize the DHCP IP address pool"""
    global dhcp_pool

    start_ip = ipaddress.IPv4Address(DHCP_POOL_START)
    end_ip = ipaddress.IPv4Address(DHCP_POOL_END)

    # Create a list of all available IPs in the range as strings
    dhcp_pool = []
    current_ip = start_ip
    while current_ip <= end_ip:
        dhcp_pool.append(str(current_ip))
        current_ip += 1

    print(f"DHCP pool initialized with {len(dhcp_pool)} IP addresses: {dhcp_pool[:5]}...")  # 显示前5个IP作为示例


def allocate_ip():
    """Allocate an IP address from the DHCP pool"""
    global dhcp_pool

    if not dhcp_pool:
        return None

    return dhcp_pool.pop(0)


def release_ip(ip):
    """Release an IP address back to the DHCP pool"""
    global dhcp_pool

    if ip not in dhcp_pool:
        dhcp_pool.append(ip)
        dhcp_pool.sort()  # Keep the pool sorted


def create_tun_interface():
    # Create a TUN interface
    TUNSETIFF = 0x400454ca
    IFF_TUN = 0x0001
    IFF_TAP = 0x0002
    IFF_NO_PI = 0x1000

    tun_fd = os.open("/dev/net/tun", os.O_RDWR)
    ifr = struct.pack('16sH', TUN_NAME, IFF_TUN | IFF_NO_PI)
    fcntl.ioctl(tun_fd, TUNSETIFF, ifr)

    return tun_fd


def setup_tun_interface():
    # Configure the TUN interface
    subprocess.run(["ip", "link", "set", "dev", "tun0", "up"])
    subprocess.run(["ip", "addr", "add", "192.168.53.1/24", "dev", "tun0"])

    # Set up NAT for the private network (适用于整个192.168.53.0/24网络)
    subprocess.run(
        ["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", "192.168.53.0/24", "-o", "eth0", "-j", "MASQUERADE"])
    subprocess.run(["iptables", "-A", "FORWARD", "-i", "tun0", "-o", "eth0", "-j", "ACCEPT"])
    subprocess.run(
        ["iptables", "-A", "FORWARD", "-i", "eth0", "-o", "tun0", "-m", "state", "--state", "RELATED,ESTABLISHED", "-j",
         "ACCEPT"])

    # 添加转发规则到10.9.0.0/24网络
    subprocess.run(["iptables", "-A", "FORWARD", "-i", "tun0", "-o", "eth1", "-j", "ACCEPT"])
    subprocess.run(
        ["iptables", "-A", "FORWARD", "-i", "eth1", "-o", "tun0", "-m", "state", "--state", "RELATED,ESTABLISHED", "-j",
         "ACCEPT"])

    # subprocess.run(["iptables", "-t", "nat", "-A", "POSTROUTING", "-s", "192.168.53.0/24", "-o", "eth1", "-j", "MASQUERADE"])


def setup_ssl_context():
    """设置 SSL 上下文"""
    # 创建服务器 SSL 上下文
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)

    # 加载服务器证书和私钥
    context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)

    # 加载受信任的 CA 证书（用于客户端验证）
    context.load_verify_locations(CA_FILE)

    # 设置验证模式（要求客户端提供证书）
    context.verify_mode = ssl.CERT_REQUIRED

    # 设置密码套件
    context.set_ciphers('ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256')

    return context


def handle_client(client_info):
    try:
        while client_info.running:
            # Wait for data from client with timeout
            try:
                ready = select.select([client_info.ssl_socket], [], [], 1.0)
                if ready[0]:
                    data = client_info.ssl_socket.recv(BUFFER_SIZE)
                    if not data:
                        break

                    # Update last active time
                    client_info.last_active = time.time()

                    # Write data to tun interface
                    os.write(tun_fd, data)
            except (socket.timeout, BlockingIOError, ssl.SSLWantReadError, ssl.SSLWantWriteError):
                # Check if client should be disconnected due to inactivity
                if time.time() - client_info.last_active > 300:  # 5 minutes timeout
                    print(f"Client {client_info.client_address} timed out")
                    break
                continue
            except Exception as e:
                print(f"Error handling client {client_info.client_address}: {e}")
                break
    except Exception as e:
        print(f"Error in client handler for {client_info.client_address}: {e}")
    finally:
        # Clean up
        client_info.ssl_socket.close()

        # Release the IP address
        release_ip(client_info.virtual_ip)

        # Remove client from list
        with client_lock:
            for ip, info in list(clients.items()):
                if info == client_info:
                    del clients[ip]
                    break

        print(f"Client disconnected: {client_info.client_address}")


def handle_tun_interface():
    while True:
        try:
            # Read data from tun interface
            data = os.read(tun_fd, BUFFER_SIZE)
            if not data:
                continue

            # Extract destination IP from IP header
            if len(data) >= 20:
                dest_ip = socket.inet_ntoa(data[16:20])
                src_ip = socket.inet_ntoa(data[12:16])

                print(f"Packet from {src_ip} to {dest_ip}")

                # Find the client with this IP
                with client_lock:
                    if dest_ip in clients:
                        # Send data to the client
                        try:
                            clients[dest_ip].ssl_socket.send(data)
                            clients[dest_ip].last_active = time.time()
                            print(f"Forwarded packet to client {dest_ip}")
                        except Exception as e:
                            print(f"Error sending data to client {dest_ip}: {e}")
                            # Remove problematic client
                            clients[dest_ip].ssl_socket.close()
                            del clients[dest_ip]
                    else:
                        # 处理发往其他网络（如10.9.0.0/24）的数据包

                        if not dest_ip.startswith("192.168.53."):

                            print(f"Forwarding packet to external network: {dest_ip}")

                        else:
                            print(f"No client found for destination {dest_ip}")
        except OSError:
            break


def cleanup_inactive_clients():
    """Periodically check for and remove inactive clients"""
    while True:
        time.sleep(60)  # Check every minute
        with client_lock:
            current_time = time.time()
            inactive_clients = []

            for ip, client_info in list(clients.items()):
                if current_time - client_info.last_active > 300:  # 5 minutes timeout
                    inactive_clients.append(ip)

            for ip in inactive_clients:
                print(f"Removing inactive client: {ip}")
                clients[ip].running = False
                clients[ip].ssl_socket.close()
                release_ip(ip)
                del clients[ip]


def check_lease_expirations():
    """Periodically check for and renew expired leases"""
    while True:
        time.sleep(300)  # Check every 5 minutes
        with client_lock:
            current_time = time.time()

            for ip, client_info in list(clients.items()):
                if current_time > client_info.lease_expiry:
                    print(f"Lease expired for client {ip}. Renewing...")
                    client_info.lease_expiry = current_time + LEASE_TIME


def main():
    global server_socket, tun_fd

    # Initialize DHCP pool
    init_dhcp_pool()

    # 设置 SSL 上下文
    ssl_context = setup_ssl_context()
    print("SSL context setup completed")

    # Create and setup TUN interface
    tun_fd = create_tun_interface()
    setup_tun_interface()

    # Create TCP server socket
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_socket.bind(('0.0.0.0', PORT))
    server_socket.listen(MAX_CLIENTS)

    # Wrap socket with SSL
    ssl_server_socket = ssl_context.wrap_socket(server_socket, server_side=True)

    print(f"TLS VPN server started on port {PORT}")

    # Start thread to handle tun interface
    tun_thread = threading.Thread(target=handle_tun_interface, daemon=True)
    tun_thread.start()

    # Start thread to cleanup inactive clients
    cleanup_thread = threading.Thread(target=cleanup_inactive_clients, daemon=True)
    cleanup_thread.start()

    # Start thread to check lease expirations
    lease_thread = threading.Thread(target=check_lease_expirations, daemon=True)
    lease_thread.start()

    try:
        while True:
            # Accept new client connections
            client_socket, client_address = ssl_server_socket.accept()
            print(f"New TLS connection from {client_address}")

            # 验证客户端证书
            try:
                cert = client_socket.getpeercert()
                if not cert:
                    print(f"Client {client_address} did not provide a certificate")
                    client_socket.close()
                    continue

                # 检查证书主题
                subject = dict(x[0] for x in cert['subject'])
                common_name = subject.get('commonName', '')
                print(f"Client certificate CN: {common_name}")

            except Exception as e:
                print(f"Certificate verification failed for {client_address}: {e}")
                client_socket.close()
                continue

            # Check if we've reached the maximum number of clients
            with client_lock:
                if len(clients) >= MAX_CLIENTS:
                    print(f"Maximum clients reached. Rejecting connection from {client_address}")
                    client_socket.close()
                    continue

            try:
                # Allocate an IP address for the client
                virtual_ip = allocate_ip()
                if not virtual_ip:
                    print(f"No available IP addresses. Rejecting connection from {client_address}")
                    client_socket.close()
                    continue

                # Send DHCP information to client
                # Format: IP (4 bytes) + subnet mask (4 bytes) + lease time (4 bytes, network order)
                subnet_mask_bytes = socket.inet_aton(SUBNET_MASK)
                virtual_ip_bytes = socket.inet_aton(virtual_ip)
                lease_time_bytes = struct.pack('!I', LEASE_TIME)

                dhcp_info = virtual_ip_bytes + subnet_mask_bytes + lease_time_bytes
                client_socket.send(dhcp_info)

                # Create client info
                client_info = ClientInfo(client_socket, client_address, virtual_ip)

                # Add client to list
                with client_lock:
                    clients[virtual_ip] = client_info

                # Start thread to handle this client
                client_thread = threading.Thread(target=handle_client, args=(client_info,))
                client_thread.start()
                client_info.thread = client_thread

                print(f"Client with virtual IP {virtual_ip} connected. Total clients: {len(clients)}")

            except Exception as e:
                print(f"Error setting up client: {e}")
                client_socket.close()
                if virtual_ip:
                    release_ip(virtual_ip)

    except KeyboardInterrupt:
        print("Shutting down server...")
    finally:
        # Close all client connections
        with client_lock:
            for ip, client_info in list(clients.items()):
                client_info.running = False
                client_info.ssl_socket.close()
                release_ip(ip)

        ssl_server_socket.close()
        server_socket.close()
        os.close(tun_fd)


if __name__ == "__main__":
    main()
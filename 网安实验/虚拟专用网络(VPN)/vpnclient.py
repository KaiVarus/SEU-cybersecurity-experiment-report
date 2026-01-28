#!/usr/bin/env python3

import os
import sys
import socket
import select
import struct
import fcntl
import subprocess
import time
import ssl

# Constants
PORT = 4433
TUN_NAME = b"tun0"
BUFFER_SIZE = 2000
RECONNECT_DELAY = 5  # seconds
CA_FILE = "ca-cert.pem"
CERT_FILE = "client-cert.pem"
KEY_FILE = "client-key.pem"


def create_tun_device():
    """创建 TUN 设备，如果不存在的话"""
    try:
        # 检查设备目录是否存在
        if not os.path.exists('/dev/net'):
            os.makedirs('/dev/net')

        # 检查 TUN 设备是否存在
        if not os.path.exists('/dev/net/tun'):
            # 创建设备节点
            subprocess.run(['mknod', '/dev/net/tun', 'c', '10', '200'], check=True)
            subprocess.run(['chmod', '0666', '/dev/net/tun'], check=True)
            print("Created TUN device /dev/net/tun")
        else:
            print("TUN device already exists")

    except Exception as e:
        print(f"Error creating TUN device: {e}")
        return False

    return True


def create_tun_interface():
    # 确保 TUN 设备存在
    if not create_tun_device():
        print("Failed to create TUN device")
        sys.exit(1)

    # Create a TUN interface
    TUNSETIFF = 0x400454ca
    IFF_TUN = 0x0001
    IFF_TAP = 0x0002
    IFF_NO_PI = 0x1000

    try:
        tun_fd = os.open("/dev/net/tun", os.O_RDWR)
        ifr = struct.pack('16sH', TUN_NAME, IFF_TUN | IFF_NO_PI)
        fcntl.ioctl(tun_fd, TUNSETIFF, ifr)

        return tun_fd
    except Exception as e:
        print(f"Error creating TUN interface: {e}")
        sys.exit(1)


def setup_tun_interface(virtual_ip, subnet_mask):
    # Configure the TUN interface
    subprocess.run(["ip", "link", "set", "dev", "tun0", "up"])
    subprocess.run(["ip", "addr", "add", f"{virtual_ip}/{subnet_mask}", "dev", "tun0"])

    # Add routes
    subprocess.run(["ip", "route", "add", "192.168.53.0/24", "dev", "tun0"])
    subprocess.run(["ip", "route", "add", "10.9.0.0/24", "via", "192.168.53.1", "dev", "tun0"])  # 通过VPN网关访问10.9.0.0/24


def setup_ssl_context(server_hostname):
    """设置 SSL 上下文"""
    # 创建客户端 SSL 上下文
    context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)

    # 加载受信任的 CA 证书
    context.load_verify_locations(CA_FILE)

    # 加载客户端证书和私钥
    try:
        context.load_cert_chain(certfile=CERT_FILE, keyfile=KEY_FILE)
    except FileNotFoundError:
        print("Client certificate not found, proceeding without client authentication")

    # 设置验证模式
    context.verify_mode = ssl.CERT_REQUIRED

    # 设置主机名检查
    context.check_hostname = True

    # 设置密码套件
    context.set_ciphers('ECDHE-RSA-AES256-GCM-SHA384:ECDHE-RSA-AES128-GCM-SHA256')

    return context


def connect_to_server(server_ip, server_hostname):
    """Connect to the VPN server and return the SSL socket and DHCP info"""
    # 设置 SSL 上下文
    ssl_context = setup_ssl_context(server_hostname)

    # Create TCP socket
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

    try:
        # Wrap socket with SSL
        print(f"Attempting to connect to {server_ip}:{PORT} with hostname {server_hostname}")
        ssl_sock = ssl_context.wrap_socket(sock, server_hostname=server_hostname)

        # Connect to server
        ssl_sock.connect((server_ip, PORT))
        print(f"TLS connection established with {server_hostname}")

        # 验证服务器证书
        cert = ssl_sock.getpeercert()
        subject = dict(x[0] for x in cert['subject'])
        common_name = subject.get('commonName', '')
        print(f"Server certificate CN: {common_name}")

        # 检查主机名是否匹配
        if common_name != server_hostname:
            print(f"Certificate hostname mismatch: expected {server_hostname}, got {common_name}")
            ssl_sock.close()
            return None, None

        # Receive DHCP information from server
        # Format: IP (4 bytes) + subnet mask (4 bytes) + lease time (4 bytes, network order)
        print("Waiting for DHCP information from server...")
        dhcp_info = ssl_sock.recv(12)
        if len(dhcp_info) != 12:
            print(f"Invalid DHCP information received from server: {len(dhcp_info)} bytes")
            ssl_sock.close()
            return None, None

        # Parse DHCP information
        virtual_ip = socket.inet_ntoa(dhcp_info[0:4])
        subnet_mask = socket.inet_ntoa(dhcp_info[4:8])
        lease_time = struct.unpack('!I', dhcp_info[8:12])[0]

        print(f"Received IP: {virtual_ip}, Subnet Mask: {subnet_mask}, Lease Time: {lease_time} seconds")

        return ssl_sock, (virtual_ip, subnet_mask, lease_time)

    except ssl.SSLError as e:
        print(f"SSL error: {e}")
        return None, None
    except ConnectionRefusedError:
        print(f"Connection refused to {server_ip}:{PORT}")
        return None, None
    except Exception as e:
        print(f"Error connecting to server: {e}")
        import traceback
        traceback.print_exc()
        return None, None


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <server_ip> <server_hostname>")
        sys.exit(1)

    server_ip = sys.argv[1]
    server_hostname = sys.argv[2]

    # Create TUN interface
    tun_fd = create_tun_interface()

    print("TLS VPN client started. Press Ctrl+C to exit.")

    while True:
        # Connect to server and get DHCP info
        ssl_sock, dhcp_info = connect_to_server(server_ip, server_hostname)
        if ssl_sock is None or dhcp_info is None:
            print(f"Failed to connect to server. Retrying in {RECONNECT_DELAY} seconds...")
            time.sleep(RECONNECT_DELAY)
            continue

        virtual_ip, subnet_mask, lease_time = dhcp_info

        # Convert subnet mask to CIDR notation
        cidr_mask = sum(bin(int(x)).count('1') for x in subnet_mask.split('.'))

        # Setup TUN interface with the assigned IP
        setup_tun_interface(virtual_ip, cidr_mask)

        # Calculate when to renew the lease
        lease_renew_time = time.time() + (lease_time / 2)

        try:
            while True:
                # Check if it's time to renew the lease
                if time.time() >= lease_renew_time:
                    print("Lease renewal time reached. Reconnecting...")
                    break

                # Wait for data from either the TUN interface or the SSL socket
                rlist, _, _ = select.select([tun_fd, ssl_sock], [], [], 1.0)

                # Data from local app -> send to server
                if tun_fd in rlist:
                    try:
                        data = os.read(tun_fd, BUFFER_SIZE)
                        if data:
                            ssl_sock.send(data)
                    except OSError:
                        print("Error reading from TUN interface")
                        break
                    except ssl.SSLWantWriteError:
                        # SSL socket needs to be written to later
                        continue

                # Data from server -> write to TUN
                if ssl_sock in rlist:
                    try:
                        data = ssl_sock.recv(BUFFER_SIZE)
                        if not data:
                            print("Server closed connection")
                            break
                        os.write(tun_fd, data)
                    except OSError:
                        print("Error reading from server")
                        break
                    except ssl.SSLWantReadError:
                        # SSL socket needs to be read from later
                        continue

        except KeyboardInterrupt:
            print("Disconnecting...")
            break
        except Exception as e:
            print(f"Error in main loop: {e}")

        finally:
            ssl_sock.close()
            print(f"Connection lost. Reconnecting in {RECONNECT_DELAY} seconds...")
            time.sleep(RECONNECT_DELAY)

    os.close(tun_fd)


if __name__ == "__main__":
    main()
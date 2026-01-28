import torch
import torch.nn as nn


class Residual(nn.Module):
    def __init__(self, fn):
        super(Residual, self).__init__()
        self.fn = fn

    def forward(self, x):
        return self.fn(x) + x


class LinearAttention(nn.Module):
    def __init__(self, dim, heads=8, dim_head=64):
        super().__init__()
        self.heads = heads
        self.dim_head = dim_head
        inner_dim = dim_head * heads
        self.to_q = nn.Linear(dim, inner_dim, bias=False)
        self.to_k = nn.Linear(dim, inner_dim, bias=False)
        self.to_v = nn.Linear(dim, inner_dim, bias=False)
        self.to_out = nn.Linear(inner_dim, dim)

    def forward(self, x):
        b, n, _, h = *x.shape, self.heads
        q = self.to_q(x).view(b, n, h, self.dim_head).transpose(1, 2)  # (b, heads, n, dim_head)
        k = self.to_k(x).view(b, n, h, self.dim_head).transpose(1, 2)
        v = self.to_v(x).view(b, n, h, self.dim_head).transpose(1, 2)

        q = torch.nn.functional.softmax(q, dim=-1)
        k = torch.nn.functional.softmax(k, dim=-1)

        context = torch.einsum('bhnd,bhne->bhde', k, v)
        out = torch.einsum('bhnd,bhde->bhne', q, context)
        out = out.transpose(1, 2).reshape(b, n, -1)
        return self.to_out(out)


class DSLAM(nn.Module):
    def __init__(self, c1, n=1, reduction=16, heads=8, dim_head=64):
        super(DSLAM, self).__init__()
        c2 = c1

        # 多尺度卷积操作
        self.DCovN = nn.Sequential(
            *[nn.Sequential(
                Residual(nn.Sequential(
                    nn.Conv2d(in_channels=c2, out_channels=c2, kernel_size=3, stride=1, padding=1, groups=c2),
                    nn.GELU(),
                    nn.BatchNorm2d(c2)
                )),
                nn.Sequential(
                    nn.Conv2d(c2, c2, kernel_size=5, padding=2, groups=c2),
                    nn.Conv2d(c2, c2, kernel_size=(1, 7), padding=(0, 3), groups=c2),
                    nn.Conv2d(c2, c2, kernel_size=(7, 1), padding=(3, 0), groups=c2),
                    nn.Conv2d(c2, c2, kernel_size=(1, 11), padding=(0, 5), groups=c2),
                    nn.Conv2d(c2, c2, kernel_size=(11, 1), padding=(5, 0), groups=c2),
                    nn.Conv2d(c2, c2, kernel_size=(1, 21), padding=(0, 10), groups=c2),
                    nn.Conv2d(c2, c2, kernel_size=(21, 1), padding=(10, 0), groups=c2),
                ),
                nn.Conv2d(in_channels=c2, out_channels=c2, kernel_size=1, stride=1, padding=0, groups=1),
                nn.GELU(),
                nn.BatchNorm2d(c2)
            ) for i in range(n)]
        )

        self.avg_pool = torch.nn.AdaptiveAvgPool2d(1)
        self.fc = nn.Sequential(
            nn.Linear(c2, c2 // reduction, bias=False),
            nn.ReLU(inplace=True),
            nn.Linear(c2 // reduction, c2, bias=False),
            nn.Sigmoid()
        )

        self.linear_attention = LinearAttention(c2, heads, dim_head)

        self._initialize_weights()
        self.initialize_layer(self.fc)

    def forward(self, x):
        b, c, _, _ = x.size()
        y = self.DCovN(x)
        y = self.avg_pool(y).view(b, c)
        y = self.fc(y).view(b, c, 1, 1)
        y = torch.exp(y)
        y = x * y.expand_as(x)

        b, c, h, w = y.size()
        y = y.view(b, c, -1).transpose(1, 2)  # (b, n, c)
        y = self.linear_attention(y)
        y = y.transpose(1, 2).view(b, c, h, w)

        return y

    def _initialize_weights(self):
        for m in self.modules():
            if isinstance(m, nn.Conv2d):
                nn.init.xavier_uniform_(m.weight, gain=1)
            elif isinstance(m, nn.BatchNorm2d):
                nn.init.constant_(m.weight, 1)
                nn.init.constant_(m.bias, 0)

    def initialize_layer(self, layer):
        if isinstance(layer, (nn.Conv2d, nn.Linear)):
            torch.nn.init.normal_(layer.weight, mean=0., std=0.001)
            if layer.bias is not None:
                torch.nn.init.constant_(layer.bias, 0)


def autopad(k, p=None, d=1):  # kernel, padding, dilation
    """Pad to 'same' shape outputs."""
    if d > 1:
        k = d * (k - 1) + 1 if isinstance(k, int) else [d * (x - 1) + 1 for x in k]  # actual kernel-size
    if p is None:
        p = k // 2 if isinstance(k, int) else [x // 2 for x in k]  # auto-pad
    return p


class Conv(nn.Module):
    """Standard convolution with args(ch_in, ch_out, kernel, stride, padding, groups, dilation, activation)."""
    default_act = nn.SiLU()  # default activation

    def __init__(self, c1, c2, k=1, s=1, p=None, g=1, d=1, act=True):
        """Initialize Conv layer with given arguments including activation."""
        super().__init__()
        self.conv = nn.Conv2d(c1, c2, k, s, autopad(k, p, d), groups=g, dilation=d, bias=False)
        self.bn = nn.BatchNorm2d(c2)
        self.act = self.default_act if act is True else act if isinstance(act, nn.Module) else nn.Identity()

    def forward(self, x):
        """Apply convolution, batch normalization and activation to input tensor."""
        return self.act(self.bn(self.conv(x)))

    def forward_fuse(self, x):
        """Perform transposed convolution of 2D data."""
        return self.act(self.conv(x))


class Bottleneck(nn.Module):
    """Standard bottleneck."""

    def __init__(self, c1, c2, shortcut=True, g=1, k=(3, 3), e=0.5):
        """Initializes a bottleneck module with given input/output channels, shortcut option, group, kernels, and
        expansion.
        """
        super().__init__()
        c_ = int(c2 * e)  # hidden channels
        self.cv1 = Conv(c1, c_, k[0], 1)
        self.cv2 = Conv(c_, c2, k[1], 1, g=g)
        self.add = shortcut and c1 == c2

    def forward(self, x):
        """'forward()' applies the YOLO FPN to input data."""
        return x + self.cv2(self.cv1(x)) if self.add else self.cv2(self.cv1(x))


class C2f_DSLAM(nn.Module):
    """C2f module with integrated DSLAM attention mechanism."""

    def __init__(self, c1, c2, n=1, shortcut=False, g=1, e=0.5):
        """Initialize C2f_SLAM layer with integrated DSLAM attention mechanism."""
        super().__init__()
        self.c = int(c2 * e)  # hidden channels
        self.cv1 = Conv(c1, 2 * self.c, 1, 1)
        self.cv2 = Conv((2 + n) * self.c, c2, 1)  # optional act=FReLU(c2)
        self.m = nn.ModuleList(Bottleneck(self.c, self.c, shortcut, g, k=((3, 3), (3, 3)), e=1.0) for _ in range(n))
        self.dslam = DSLAM(c2, n)

    def forward(self, x):
        """Forward pass through C2f_DSLAM layer."""
        y = list(self.cv1(x).chunk(2, 1))
        y.extend(m(y[-1]) for m in self.m)
        y = self.cv2(torch.cat(y, 1))
        y = self.dslam(y)
        return y

    def forward_split(self, x):
        """Forward pass using split() instead of chunk() with DSLAM attention."""
        y = list(self.cv1(x).split((self.c, self.c), 1))
        y.extend(m(y[-1]) for m in self.m)
        y = self.cv2(torch.cat(y, 1))
        y = self.dslam(y)
        return y
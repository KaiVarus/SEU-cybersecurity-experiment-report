import torch
from torch import nn


class DEMAttention(nn.Module):
    def __init__(self, channels, factor=32):
        super(DEMAttention, self).__init__()
        self.groups = factor
        assert channels // self.groups > 0
        self.softmax = nn.Softmax(-1)
        self.agp = nn.AdaptiveAvgPool2d((1, 1))
        self.pool_h = nn.AdaptiveAvgPool2d((None, 1))
        self.pool_w = nn.AdaptiveAvgPool2d((1, None))
        self.gn = nn.GroupNorm(channels // self.groups, channels // self.groups)

        # 多尺度卷积核
        self.dconv5_5 = nn.Conv2d(channels // self.groups, channels // self.groups, kernel_size=5, padding=2,
                                  groups=channels // self.groups)
        self.dconv1_7 = nn.Conv2d(channels // self.groups, channels // self.groups, kernel_size=(1, 7), padding=(0, 3),
                                  groups=channels // self.groups)
        self.dconv7_1 = nn.Conv2d(channels // self.groups, channels // self.groups, kernel_size=(7, 1), padding=(3, 0),
                                  groups=channels // self.groups)
        self.dconv1_11 = nn.Conv2d(channels // self.groups, channels // self.groups, kernel_size=(1, 11),
                                   padding=(0, 5), groups=channels // self.groups)
        self.dconv11_1 = nn.Conv2d(channels // self.groups, channels // self.groups, kernel_size=(11, 1),
                                   padding=(5, 0), groups=channels // self.groups)

        self.conv1x1 = nn.Conv2d(channels // self.groups, channels // self.groups, kernel_size=1, stride=1, padding=0)
        self.conv3x3 = nn.Conv2d(channels // self.groups, channels // self.groups, kernel_size=3, stride=1, padding=1)

    def forward(self, x):
        b, c, h, w = x.size()
        group_x = x.reshape(b * self.groups, -1, h, w)  # b*g,c//g,h,w

        # 行、列池化
        x_h = self.pool_h(group_x)
        x_w = self.pool_w(group_x).permute(0, 1, 3, 2)

        # 多尺度卷积操作
        hw = self.conv1x1(torch.cat([x_h, x_w], dim=2))
        x_h, x_w = torch.split(hw, [h, w], dim=2)

        # 多尺度卷积特征提取
        x_init = group_x * x_h.sigmoid() * x_w.permute(0, 1, 3, 2).sigmoid()
        x1 = self.dconv5_5(x_init)
        x2 = self.dconv1_7(x_init)
        x3 = self.dconv7_1(x_init)
        x4 = self.dconv1_11(x_init)
        x5 = self.dconv11_1(x_init)

        # 将多尺度卷积结果相加
        x_multi_scale = x1 + x2 + x3 + x4 + x5 + x_init

        # 使用GN正则化后的卷积和Softmax操作
        x_multi_scale_gn = self.gn(x_multi_scale)
        x2_conv = self.conv3x3(x_multi_scale_gn)

        # 计算权重
        x11 = self.softmax(self.agp(x_multi_scale_gn).reshape(b * self.groups, -1, 1).permute(0, 2, 1))
        x12 = x2_conv.reshape(b * self.groups, c // self.groups, -1)  # b*g, c//g, hw
        x21 = self.softmax(self.agp(x2_conv).reshape(b * self.groups, -1, 1).permute(0, 2, 1))
        x22 = x_multi_scale_gn.reshape(b * self.groups, c // self.groups, -1)  # b*g, c//g, hw
        weights = (torch.matmul(x11, x12) + torch.matmul(x21, x22)).reshape(b * self.groups, 1, h, w)

        # 输出特征
        return (group_x * weights.sigmoid()).reshape(b, c, h, w)


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


class C2f_DEMAttention(nn.Module):
    """CSP Bottleneck with 2 convolutions followed by DEMAttention attention."""

    def __init__(self, c1, c2, n=1, shortcut=False, g=1, e=0.5):
        """Initialize CSP bottleneck layer with two convolutions with DEMAttention attention."""
        super().__init__()
        self.c = int(c2 * e)  # hidden channels
        self.cv1 = Conv(c1, 2 * self.c, 1, 1)
        self.cv2 = Conv((2 + n) * self.c, c2, 1)  # optional act=FReLU(c2)
        self.m = nn.ModuleList(Bottleneck(self.c, self.c, shortcut, g, k=((3, 3), (3, 3)), e=1.0) for _ in range(n))
        self.dema = DEMAttention(c2)

    def forward(self, x):
        """Forward pass through C2f layer followed by DEMAttention attention."""
        y = list(self.cv1(x).chunk(2, 1))
        y.extend(m(y[-1]) for m in self.m)
        out = self.cv2(torch.cat(y, 1))
        return self.dema(out)

    def forward_split(self, x):
        """Forward pass using split() instead of chunk() followed by DEMAttention attention."""
        y = list(self.cv1(x).split((self.c, self.c), 1))
        y.extend(m(y[-1]) for m in self.m)
        out = self.cv2(torch.cat(y, 1))
        return self.dema(out)


"""RGB -> YCbCr (BT.601, integer), 4:2:0 subsampling and 8x8 blocking.

All arithmetic is integer so a Verilog implementation can be bit-exact:
    Y  = (77 R + 150 G + 29 B + 128) >>> 8
    Cb = ((-43 R - 85 G + 128 B + 128) >>> 8) + 128
    Cr = ((128 R - 107 G - 21 B + 128) >>> 8) + 128
(>>> = arithmetic shift right, i.e. floor division by 256), clamped to 0..255.

4:2:0 chroma = (a + b + c + d + 2) >> 2 over each 2x2 neighbourhood.

Block order inside one 16x16 MCU (interface contract): Y0 Y1 Y2 Y3 Cb Cr, where
Y0 = top-left, Y1 = top-right, Y2 = bottom-left, Y3 = bottom-right.
Samples inside a block are row-major. MCUs are in raster order.
"""
import numpy as np


def pad_to_mcu(rgb):
    """Edge-replicate the frame so height and width are multiples of 16."""
    h, w = rgb.shape[:2]
    ph, pw = (-h) % 16, (-w) % 16
    if ph or pw:
        rgb = np.pad(rgb, ((0, ph), (0, pw), (0, 0)), mode="edge")
    return rgb


def rgb_to_ycbcr(rgb):
    rgb = rgb.astype(np.int32)
    R, G, B = rgb[..., 0], rgb[..., 1], rgb[..., 2]
    Y = (77 * R + 150 * G + 29 * B + 128) >> 8
    Cb = ((-43 * R - 85 * G + 128 * B + 128) >> 8) + 128
    Cr = ((128 * R - 107 * G - 21 * B + 128) >> 8) + 128
    return (np.clip(Y, 0, 255), np.clip(Cb, 0, 255), np.clip(Cr, 0, 255))


def subsample_420(c):
    c = c.astype(np.int32)
    return (c[0::2, 0::2] + c[0::2, 1::2] + c[1::2, 0::2] + c[1::2, 1::2] + 2) >> 2


def to_mcu_blocks(Y, Cb, Cr):
    """Returns int32 array (n_mcu, 6, 8, 8) in the contract's block order."""
    H, W = Y.shape
    mr, mc = H // 16, W // 16
    y = Y.reshape(mr, 2, 8, mc, 2, 8).transpose(0, 3, 1, 4, 2, 5).reshape(mr * mc, 4, 8, 8)
    cb = Cb.reshape(mr, 8, mc, 8).transpose(0, 2, 1, 3).reshape(mr * mc, 1, 8, 8)
    cr = Cr.reshape(mr, 8, mc, 8).transpose(0, 2, 1, 3).reshape(mr * mc, 1, 8, 8)
    return np.concatenate([y, cb, cr], axis=1).astype(np.int32)

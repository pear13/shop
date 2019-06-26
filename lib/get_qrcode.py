import os
import logging

from PIL import Image, ImageFont, ImageDraw
log = logging.getLogger()
tplroot = os.path.dirname(__file__)


def addText(wImg, name, price, detail):
    """
     name, price, detail
    用户名 商品价格 商品详情  安利 长按识别
    :return:
    """
    font_22 = ImageFont.truetype(tplroot + '/PingFang.ttf', 22)
    font_24 = ImageFont.truetype(tplroot + '/PingFang.ttf', 24)
    font_32 = ImageFont.truetype(tplroot + '/PingFang.ttf', 32)
    draw = ImageDraw.Draw(wImg)
    text_name = (wImg.size[0] - 397, wImg.size[1] - 779)  # 分享人name
    text_a = (wImg.size[0] - 397, wImg.size[1] - 742)  # 安利
    text_price = (wImg.size[0] - 493, wImg.size[1] - 179)  # 价格
    text_detail1 = (wImg.size[0] - 493, wImg.size[1] - 117)  # 商品详情
    text_detail2 = (wImg.size[0] - 493, wImg.size[1] - 78)  # 商品详情
    text_c = (wImg.size[0] - 202, wImg.size[1] - 70)  # 长按识别
    draw.text(text_name, name, fill=(136, 136, 136), font=font_22)
    draw.text(text_a, '反手就是一个安利，请接好~', fill=(51, 51, 51), font=font_24)
    draw.text(text_price, price, fill=(51, 51, 51), font=font_32)
    if len(detail) <= 10:
        draw.text(text_detail1, detail, fill=(51, 51, 51), font=font_24)
    if len(detail) < 20:
        draw.text(text_detail1, detail[0: 10], fill=(51, 51, 51), font=font_24)
        draw.text(text_detail2, detail[10:], fill=(51, 51, 51), font=font_24)
    else:
        detail1 = detail[10:19] + '...'
        print(detail1)
        draw.text(text_detail1, detail[0: 10], fill=(51, 51, 51), font=font_24)
        draw.text(text_detail2, detail1, fill=(51, 51, 51), font=font_24)
    draw.text(text_c, '长按识别查看商品', fill=(136, 136, 136), font=font_22)
    ImageDraw.Draw(wImg)
    return '海报添加文字成功'
    pass


def addAva(wImg, avaImg):
    """
    添加头像
    :return:
    """
    r3 = 35
    r2 = 70
    avaImg = avaImg.resize((r3 * 2, r3 * 2), Image.ANTIALIAS).convert("RGB")
    avaImgb = Image.new('RGB', (r3 * 2, r3 * 2), 'white')
    pima = avaImg.load()
    pimb = avaImgb.load()
    r = float(r2 / 2)
    for i in range(r2):
        for j in range(r2):
            lx = abs(i - r)
            ly = abs(j - r)
            ll = (pow(lx, 2) + pow(ly, 2)) ** 0.5
            if ll < r3:
                pimb[i - (r - r3), j - (r - r3)] = pima[i, j]

    img_ava = (wImg.size[0] - 488, wImg.size[1] - 781)
    wImg.paste(avaImgb, img_ava)
    return '添加头像成功'


def addSpu(wImg, spuImg):
    """
    添加商品图片
    :return:
    """
    left = top = 0
    w = spuImg.size[0]
    h = spuImg.size[1]
    if w < h:
        top = (h - w) / 2
        bottom = top + w
        right = w
    else:
        left = (w - h) / 2
        right = left + h
        bottom = h

    spuImg = spuImg.crop((left, top, right, bottom)).resize((468, 435), Image.ANTIALIAS)

    img_spu = (wImg.size[0] - 493, wImg.size[1] - 679)
    wImg.paste(spuImg, img_spu)
    return '商品图片成功'


def addCode(wImg, codeImg):
    """
    添加二维码
    :return:
    """
    codeImg = codeImg.resize((138, 137), Image.ANTIALIAS)

    img_code = (wImg.size[0] - 181, wImg.size[1] - 224)
    wImg.paste(codeImg, img_code)
    return '添加二维码成功'


def sharePoster(name, price, detail, avaImg, spuImg, codeImg):
    """
    生成商品分享海报
    :return:
    """
    wImg = Image.new('RGB', (518, 811), 'white')
    addText(wImg, name, price, detail)
    addAva(wImg, avaImg)
    addSpu(wImg, spuImg)
    addCode(wImg, codeImg)
    return wImg


# if __name__ == '__main__':
#     # avaImg = Image.open(tplroot + '/img/ava.png').convert("RGBA")
#     # spuImg = Image.open(tplroot + '/img/spu.png')
#     codeImg = Image.open(tplroot + '/img/3_32_code.png')
#     print(codeImg, '+++++++++++')
#     sharePoster('用户名', '￥100.00', '商品详情详情详情商品哈哈哈哈哈哈哈哈哈额', codeImg)
#     # print(sharePoster('用户名', '￥100.00', '商品详情详情详情商品哈哈哈哈哈哈哈哈哈额', codeImg))


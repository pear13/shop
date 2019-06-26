from django import forms

from .models import *


class HomeCateForm(forms.ModelForm):
    cate = forms.ModelChoiceField(Cate.objects.all(), label='分类')

    class Meta:
        model = HomeCate
        fields = ['index', 'cate']


class Cate2Form(forms.ModelForm):
    cate = forms.ModelChoiceField(Cate.objects.all(), label='父分类')

    class Meta:
        model = Cate2
        fields = ['name', 'cate', 'cover', 'cnt']


class SpuForm(forms.ModelForm):
    cate = forms.ModelChoiceField(Cate.objects.all(), label='分类')
    ship = forms.ModelChoiceField(Ship.objects.all(), label='运费')

    class Meta:
        model = Spu

        fields = '__all__'


class ShipForm(forms.ModelForm):
    prov = forms.ModelChoiceField(District.objects.all(), label='指定省份', required=False)

    class Meta:
        model = Ship
        exclude = ['onProv']


class SpuTagForm(forms.ModelForm):
    title = forms.ModelChoiceField(Spu.objects.all(), label='商品名')
    name = forms.ModelChoiceField(Tag.objects.all(), label='标签名')

    class Meta:
        model = SpuTag
        fields = ['appid', 'title', 'name']


class SpuImgForm(forms.ModelForm):
    title = forms.ModelChoiceField(Spu.objects.all(), label='商品名')

    class Meta:
        model = SpuImg
        exclude = ['spuId']


class SpuContentForm(forms.ModelForm):
    title = forms.ModelChoiceField(Spu.objects.all(), label='商品名')

    class Meta:
        model = SpuContent
        exclude = ['spuId']


class SkuForm(forms.ModelForm):
    title = forms.ModelChoiceField(Spu.objects.all(), label='商品名')

    class Meta:
        model = Sku
        exclude = ['spuId']


class ShipProvForm(forms.ModelForm):
    ship = forms.ModelChoiceField(Ship.objects.all(), label='运费规则')
    prov = forms.ModelChoiceField(District.objects.filter(), label='省份名称')

    class Meta:
        model = ShipProv
        exclude = ['shipId', 'provId']


class SpuServForm(forms.ModelForm):
    title = forms.ModelChoiceField(Spu.objects.all(), label='商品名')

    class Meta:
        model = Spec
        exclude = ['spuId']

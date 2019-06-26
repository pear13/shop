# 测试case
# 只需要在JkbTest里定义test_开头的函数即可
# pycharm可以点击 测试类或测试类中方法左边绿色三角形即可执行
# 执行测试时会创建数据库，执行完后会删除
#

import unittest
from django.test import TestCase, Client
from django.http import response
import requests


from main.models import User

TOKEN = 'eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJleHAiOjE1NTkwMjEzOTMsImFwcGlkIjoic2FkZmZmZmZmIiwidXNlcmlkIjoxLCJmcm9tIjoibWluIn0.fTAvPsUNL0J6hRTGIpUP_f_uDvo3FXiZ6uM93ZMpmT0'


class JkbTest(TestCase):
    """
    聚客宝测试用例
    """

    def setUp(self) -> None:
        """
        初始化测试数据, 每执行一个测试单元都会调用
        :return:
        """
        self.token = ''
        u = User.objects.update_or_create(**{
            'id': 2,
            'appid': 'tes_appid',
            'name': 'tes',
            'avatar': 'avatar',
            'phone': '17006697457',
            'birth': '2019-01-01',
            'sex': 0,
            'openid': 'tes_openid',
            'unionid': '',
            'apikey': 'tesApiKey'
        })

        print('user created------->', u)

    def test_index(self):
        rsp = self.client.get('/')

        self.assertIn('token', rsp.json())

    def test_login(self):

        rsp = self.client.post('/login', data={
            'appid': 'tes_appid',
            'openid': 'tes_openid'
        })

        data = rsp.json()

        self.assertEqual(rsp.status_code, 200, '请求异常')
        self.assertEqual(data['code'], 0, '返回异常')
        self.token = data['token']

    def test_tes(self):
        # self.test_login()
        # rsp = self.client.get('/tes', HTTP_jkbtoken=self.token)
        rsp = requests.get('http://127.0.0.1:8001/tes', headers={'jkbtoken': TOKEN})
        self.assertEqual(rsp.status_code, 200)
        self.assertEqual(rsp.json()['code'], 0)



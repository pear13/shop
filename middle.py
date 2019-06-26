#  请求日志中间件
import json
import logging

import jwt
from django.utils import timezone

from lib import gen_resp, RespData, Code
from lib.signals import signal_first_visit

log = logging.getLogger()


class AuthMiddle(object):
    """
    计时兼异常处理, 逻辑已经放到deco里, 暂时不用
    """

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):

        # 黑名单处理

        path = str(request.path)

        # 接口关闭csrf检测
        if not path.startswith('/admin'):
            request._dont_enforce_csrf_checks = True

        # 接口token检测
        is_except_path = path.startswith('/admin') or \
            (path.startswith('/openid') and request.method == 'GET') or\
            (path.startswith('/login') and request.method == 'POST') or\
            (path.startswith('/payNoti') and request.method == 'POST') or\
            (path.startswith('/media/') and request.method == 'GET')

        request.APPID = request.headers.get('APPID')
        if not path.startswith('/admin') and not request.APPID and not path.startswith('/payNoti') and not path.startswith('/media/'):  # 除了admin都要检测请求头中是否有APPID + 回调
            return gen_resp(Code.ILLEGAL)

        if not is_except_path:

            start = timezone.now()

            token = request.headers.get('AUTHTOKEN')
            if not token:
                return gen_resp(Code.ILLEGAL)
            try:
                data = jwt.decode(token, verify=False)
                from main.models import User
                user: User = User.objects.filter(id=data.get('uid'), appid=request.APPID).first()
                if user is None:
                    return gen_resp(Code.USER_NOT_FOUND)
                jwt.decode(token, user.apikey, algorithms=['HS256'])
            except jwt.ExpiredSignatureError:
                return gen_resp(Code.TOKEN_EXPIRED)
            except Exception as e:
                log.warning(f'token异常：{e}')
                return gen_resp(Code.TOKEN_EXPIRED)
            request.user = user

            before = ['=' * 40, request.get_raw_uri()]
            if request.content_type in ['application/xml', 'application/json']:
                before.append('body>\n' + request.body.decode())
            elif request.content_type == 'application/x-www-form-urlencoded':
                before.append('form>\n' + str(request.POST.dict()))
            log.info('\n'.join(before))

        response = self.get_response(request)

        if not is_except_path and (response['Content-Type'] in ['application/json']):
            log.info('\n'.join(['\nresp>\n' + response.content.decode(),
                                '=' * 40 + ' cost time:' + str(timezone.now() - start)]))

        # 发送信号
        if path.startswith('/homeCate') or path.startswith('/cate') or path.startswith('/spuDetail'):
            shareBy = request.GET.get('shareBy')
            markId = request.GET.get('markId')
            log.info("shareBy{}markId{}" .format(shareBy, markId))
            signal_first_visit.send(sender=None, appid=request.APPID, markId=markId, userId=request.user.id,
                                    shareBy=shareBy)
            log.info('end---------signal')

        return response

    def process_exception(self, request, exception):
        """
        统一处理错误返回
        :param request:
        :param exception:
        :return:
        """

        data = {'code': 10001, 'msg': '未知异常'}

        if isinstance(exception, RespData):
            data = exception.data
        else:
            log.warning(exception)

        return gen_resp(**data)



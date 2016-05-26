# -*- coding: utf-8 -*-
"""
    test_two_factor
    ~~~~~~~~~~~~~~~~~

    two_factor tests
"""

import onetimepass
import pytest

from utils import logout
from flask_security.utils import SmsSenderBaseClass, SmsSenderFactory

pytestmark = pytest.mark.two_factor()


class SmsTestSender(SmsSenderBaseClass):
    SmsSenderBaseClass.messages = []
    SmsSenderBaseClass.count = 0

    def __init__(self):
        super(SmsSenderBaseClass, self).__init__()

    def send_sms(self, from_number, to_number, msg):
        SmsSenderBaseClass.messages.append(msg)
        SmsSenderBaseClass.count += 1
        return

    def get_count(self):
        return SmsSenderBaseClass.count

SmsSenderFactory.senders['test'] = SmsTestSender


class TestMail():

    def __init__(self):
        self.count = 0
        self.msg = ""

    def send(self, msg):
        self.msg = msg
        self.count += 1


def test_two_factor_flag(app, client, get_message):

    # trying to pick method without doing earlier stage
    data = dict(setup="mail")
    response = client.post('/login/two_factor_setup_function', data=data, follow_redirects=True)
    assert 'You currently do not have permissions to access this page' in response.data

    # trying to verify code without going through two factor first login function
    wrong_code = '000000'
    response = client.post('/login/two_factor_token_validation', data=dict(code=wrong_code))
    assert response.status_code == 302

    # Test login using invalid email
    data = dict(email="nobody@lp.com", password="password")
    response = client.post('/login', data=data)
    assert 'Specified user does not exist' in response.data
    json_data = '{"email": "nobody@lp.com", "password": "password"}'
    response = client.post('/login', data=json_data, headers={'Content-Type': 'application/json'})
    assert 'Specified user does not exist' in response.data

    # Test login using valid email and invalid password
    data = dict(email="gal@lp.com", password="wrong_pass")
    response = client.post('/login', data=data)
    assert 'Invalid password' in response.data
    json_data = '{"email": "gal@lp.com", "password": "wrong_pass"}'
    response = client.post('/login', data=json_data, headers={'Content-Type': 'application/json'})
    assert 'Invalid password' in response.data

    # Test two factor authentication first login
    data = dict(email="matt@lp.com", password="password")
    response = client.post('/login', data=data, )
    assert 'Two-factor authentication adds an extra layer of security' in response.data
    response = client.post('/login/two_factor_setup_function', data=dict(setup="not_a_method"),
                           follow_redirects=True)
    assert 'Marked method is not valid' in response.data

    # test first login using json data
    json_data = dict(email="dave@lp.com", password="password")
    response = client.post('/login', data=json_data, headers={'Content-Type': 'application/json'},
                           follow_redirects=True)
    # try non-existing setup on this page
    json_data = '{"setup": "not_a_method"}'
    response = client.post('/login/two_factor_setup_function', data=json_data,
                           headers={'Content-Type': 'application/json'}, follow_redirects=True)
    assert '"response": {}' in response.data

    json_data = '{"setup": "mail"}'
    response = client.post('/login/two_factor_setup_function', data=json_data,
                           headers={'Content-Type': 'application/json'}, follow_redirects=True)
    json_data = '{"code": "00000"}'
    response = client.post('/login/two_factor_token_validation', data=json_data,
                           headers={'Content-Type': 'application/json'}, follow_redirects=True)
    assert '"response": {}' in response.data

    # Test for sms in process of valid login
    sms_sender = SmsSenderFactory.createSender('test')
    json_data = '{"email": "gal@lp.com", "password": "password"}'
    response = client.post('/login', data=json_data, headers={'Content-Type': 'application/json'})
    assert response.status_code == 200
    assert sms_sender.get_count() == 1

    code = sms_sender.messages[0].split()[-1]

    # submit bad token to two_factor_token_validation
    response = client.post('/login/two_factor_token_validation', data=dict(code=wrong_code),
                           follow_redirects=True)
    assert 'Invalid Token' in response.data

    # sumbit right token and show appropriate response
    response = client.post('/login/two_factor_token_validation', data=dict(code=code),
                           follow_redirects=True)
    assert 'Your token has been confirmed' in response.data

    # try confirming password with a wrong one
    response = client.post('/change/two_factor_change_method_password_confirmation',
                           data=dict(password=""), follow_redirects=True)
    assert 'Invalid password' in response.data

    # try confirming password with a wrong one + json
    json_data = '{"password": "wrong_password"}'
    response = client.post('/change/two_factor_change_method_password_confirmation',
                           data=json_data, headers={'Content-Type': 'application/json'},
                           follow_redirects=True)
    assert 'Invalid password' in response.data

    # Test change two_factor password confirmation view
    password = 'password'
    response = client.post('/change/two_factor_change_method_password_confirmation',
                           data=dict(password=password), follow_redirects=True)
    assert 'You successfully confirmed password' in response.data
    assert 'Two-factor authentication adds an extra layer of security' in response.data

    # change method (from sms to mail)
    setup_data = dict(setup='mail')
    testMail = TestMail()
    app.extensions['mail'] = testMail
    response = client.post('/login/two_factor_setup_function', data=setup_data,
                           follow_redirects=True)
    assert 'To complete logging in, please enter the code sent to your mail' in response.data

    code = testMail.msg.body.split()[-1]
    # sumbit right token and show appropriate response
    response = client.post('/login/two_factor_token_validation', data=dict(code=code),
                           follow_redirects=True)
    assert 'You successfully changed your two factor method' in response.data

    logout(client)

    # Test for google_authenticator (test)
    json_data = '{"email": "gal2@lp.com", "password": "password"}'
    response = client.post('/login', data=json_data, headers={'Content-Type': 'application/json'})
    assert response.status_code == 200   # Why Get me to rescue from ??

    totp_secret = u'RCTE75AP2GWLZIFR'
    code = str(onetimepass.get_totp(totp_secret))
    response = client.post('/login/two_factor_token_validation', data=dict(code=code),
                           follow_redirects=True)
    assert 'Your token has been confirmed' in response.data

    logout(client)

    # Test two factor authentication first login
    data = dict(email="matt@lp.com", password="password")
    response = client.post('/login', data=data, follow_redirects=True)
    assert 'Two-factor authentication adds an extra layer of security' in response.data

    # check availability of qrcode page when this option is not picked
    qrcode_page_response = client.get('/login/two_factor_qrcode')
    assert qrcode_page_response.status_code == 302

    # check availability of qrcode page when this option is picked
    setup_data = dict(setup='google_authenticator')
    response = client.post('/login/two_factor_setup_function', data=setup_data,
                           follow_redirects=True)
    assert 'Open Google Authenticator on your device' in response.data
    qrcode_page_response = client.get('/login/two_factor_qrcode', data=setup_data)

    # check appearence of setup page when sms picked and phone number entered
    sms_sender = SmsSenderFactory.createSender('test')
    data = dict(setup='sms', phone="+111111111111")
    response = client.post('/login/two_factor_setup_function', data=data, follow_redirects=True)
    assert 'To Which Phone Number Should We Send Code To' in response.data
    assert sms_sender.get_count() == 2
    code = sms_sender.messages[1].split()[-1]

    response = client.post('/login/two_factor_token_validation', data=dict(code=code),
                           follow_redirects=True)
    assert 'Your token has been confirmed' in response.data

    logout(client)
    # check the two factor help/rescue function
    rescue_data = dict(help_setup='lost_device')
    rescue_data_json = '{"help_setup": "lost_device"}'
    response = client.post('/login/two_factor_rescue_function', data=rescue_data_json,
                           headers={'Content-Type': 'application/json'})
    assert '"response": {}' in response.data
    data = dict(email="gal2@lp.com", password="password")
    response = client.post('/login', data=data)
    assert 'Please enter your authentication code' in response.data
    response = client.post('/login/two_factor_rescue_function', data=rescue_data)
    assert 'The code for authentication was sent to your email address' in response.data
    rescue_data = dict(help_setup='no_mail_access')
    response = client.post('/login/two_factor_rescue_function', data=rescue_data)
    assert 'A mail was sent to us in order to reset your application account' in response.data

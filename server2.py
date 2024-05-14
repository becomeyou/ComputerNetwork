import threading
import time
import os
import handleGET
import handleHEAD
import argparse
import base64
from socket import *
from threading import Thread
from pathlib import Path
from datetime import datetime

import handlePOST

ENCODING = 'utf-8'
CRLF = '\r\n'
ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data') 

Accounts = {}
Cookie = {}
sessions = {}
encryption = False
cookie_cnt = 0


def response_401():
    return b"HTTP/1.1 401 Unauthorized\r\nWWW-Authenticate: Basic realm=\"Authorization Required\"\r\nContent-Length: 0\r\n\r\n"

def response_405():
    return b"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n405 Method Not Allowed"

def generate_session_id():
    global cookie_cnt
    cookie_cnt += 1
    return cookie_cnt

# 创建会话
def create_session():

    session_id = generate_session_id()
    # 设置过期时间为600秒
    sessions[session_id] = time.time() + 10
    return session_id

# 清理过期会话
def cleanup_sessions():
    current_time = time.time()
    expired_sessions = [s for s, exp_time in sessions.items() if exp_time < current_time]
    for s in expired_sessions:
        sessions.pop(s)
        Cookie.pop(str(s))
        print(f'cleaned:{s}')
    # 每10秒运行一次清理
    threading.Timer(10, cleanup_sessions).start()

def getCookie(lines):
    for line in lines:
        if line.startswith('Cookie:'):
            cookie = line.split(';')[0].split('=')[1]
            if cookie not in Cookie:
                return None, -2
            else:
                return cookie, 0
    return None, -1

def Load_Accounts():
    with open('./accounts.txt') as file:
        while True:
            content = file.readline()
            if (':' not in content):
                break
            username, password = content.split(':')
            password = password[:-1]
            Accounts[username] = password

def Save_Public_Key():
    with open('./data/public_key.txt','w') as file:
        file.write(f'{public_key[0]}, {public_key[1]}')


def Generate_Resp_Header(status, info):
    header = 'HTTP/1.1 ' + status + CRLF  # Startline
    for k, v in info.items():
        header = header + k + ': ' + v + CRLF
    return header


def pow_Mod(x, y, Mod):
    res = 1
    while (y > 0):
        if (y & 1):
            res = res * x % Mod
        x = x * x % Mod
        y //= 2
    return res


key_p = 823
key_q = 1039
key_N = key_p * key_q
key_phiN = (key_p - 1) * (key_q - 1)
key_e = 269
key_d = pow_Mod(key_e, 280703, key_phiN)
key_client = None
public_key = (key_e, key_N)
private_key = (key_d, key_N)


def Key_Decrypt(encrypted_key):
    return pow_Mod(encrypted_key, key_d, key_N)


def Encrypt(M,key):
    msg = b''
    for s in M:
        msg += ((s + key) % 256).to_bytes()
    return msg

def Decrypt(M,key):
    msg = b''
    for s in M:
        msg += ((s - key) % 256).to_bytes()
    return msg


# def Generate_Resp(status, data):
#     info = {}  # dict{str:str}
#     global cookie_state
#     global cookie_cnt
#     body = data
#     info['Date'] = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
#     info['Connection'] = 'Keep-Alive'
#     info['Content-Length'] = str(len(body.encode(ENCODING)))
#     if (encryption):
#         info['Encryption'] = 'public-key=' + str(public_key)
#     if (cookie_state == -1):
#         cookie_cnt += 1
#         Cookie.append(cookie_cnt)
#         info['Set-Cookie'] = 'session-id=' + str(cookie_cnt)

#     header = Generate_Resp_Header(status, info)
#     msg = header + CRLF + body
#     return msg


def HandleRequest(conn, request_data, key_client):
    print(b'origin data:'+request_data)
    if(key_client is not None):
        request_data = Decrypt(request_data,key_client)
        print(b'Decrypted data:'+request_data)
    header,body = request_data.split(b'\r\n\r\n', 1)
    header = header.decode(ENCODING)
    username = None
    response = None
    Closing = False
    lines = header.split(CRLF)

    cookie,cookie_state = getCookie(lines)
    if cookie_state == -2:
        response = response_401()
    elif cookie_state == 0:
        username = Cookie[cookie]
        cookie = None

    for line in lines[1:]:  # header processing
        if (line.startswith('Connection: Close')):
            Closing = True
        elif (cookie_state < 0 and line.startswith('Authorization: ')):
            auth = base64.b64decode(line.split('Basic ')[1]).decode('utf-8')
            username = auth.split(':')[0]
            pwd = auth.split(':')[1]
            if (username in Accounts):
                if (pwd == Accounts[username]):
                    cookie = str(create_session())
                    Cookie[cookie] = username
                else:
                    response = response_401()
                    return response, Closing , key_client
            else:
                response = response_401()
                return response, Closing, key_client

        elif (encryption and line.startswith('Encryption: ')):
            key_client = Key_Decrypt(int(line.split('key=')[1]))
            print(f'Getkey:{key_client}')
        # elif:
        # pass  # TODO
    # TODO
    url = lines[0].split(' ')[1]
    if(username is not None):
        if (url.startswith('/upload') or url.startswith('/delete')):
            if cookie_state == -1:
                response = handlePOST.handlePost(conn, header, body, username, cookie)
            else:
                response = handlePOST.handlePost(conn, header, body, username)
        elif (lines[0].startswith('GET')):
            response = handleGET.HandleGET(conn, request_data, cookie)
        elif (lines[0].startswith('HEAD')):
            response = handleHEAD.HandleHEAD(conn, request_data, cookie)
        else:
            response = response_405()
    else:
        response = response_401()

    if (key_client is not None):
        response = Encrypt(response,key_client)

    method, full_path, _ = lines[0].split()
    path, _, query = full_path.partition('?')
    path = path.lstrip('/')
    abs_path = Path(os.path.join(DATA_DIR, path))
    if( abs_path.is_file() and method != 'GET'):
        response = response_405()
        
    return response, Closing, key_client


def HandleConn(conn, addr):
    print('connection started')
    sendmsg = ''
    isClosing = False
    key = None
    with conn:
        while True:
            request_data = conn.recv(1024)
            if not request_data:
                continue
            sendmsg, isClosing, key = HandleRequest(conn, request_data, key)
            if sendmsg is not None:
                # conn.sendall(sendmsg.encode(ENCODING))
                conn.sendall(sendmsg)

            if (isClosing == True):
                break

    print('connection close')


# if __name__ == '__main__':
parser = argparse.ArgumentParser()
parser.add_argument("-i", "--host", type=str, default='localhost')
parser.add_argument("-p", "--port", type=int, default=8080)
parser.add_argument("-e", "--encryption", action='store_true')
args = parser.parse_args()
host = args.host
port = args.port
encryption = args.encryption

Load_Accounts()
if(encryption):
    Save_Public_Key()

ss = socket(AF_INET, SOCK_STREAM)
addr = (host, port)
ss.bind(addr)

cleanup_sessions()
threads = []
ss.listen()
ss.settimeout(2)  # set timeout to stop blocking and capture Ctrl+C
try:
    while True:
        try:
            # print('waiting...')
            conn, addr = ss.accept()
            print('client accepted')
            th = Thread(target=HandleConn, args=(conn, addr))
            th.start()
            threads.append(th)
        except timeout as e:
            pass
except Exception as e:
    print(e)
finally:
    ss.close()
    print('server closed')

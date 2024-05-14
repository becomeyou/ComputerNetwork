from socket import *
import base64

cs = socket(AF_INET,SOCK_STREAM)
host = 'localhost'
port = 8080
addr = (host,port)


ENCODING = 'utf-8'
CRLF = '\r\n'

def Generate_Req_Header(url, method, info):
    header = method + ' ' + url + ' HTTP/1.1' + CRLF # Startline
    for k,v in info.items():
        header = header + k + ': ' + v + CRLF
    return header

def Generate_Req(url,method,inputmsg):
    info = {}
    if(inputmsg == 'quit'):
        data = 'quit'
        info['Connection'] = 'Close'
    else:
        data = inputmsg
        info['Connection'] = 'Keep-Alive'

    body = data + CRLF
    info['Host'] = host +':'+ str(port)
    info['Content-Length'] = str(len(body.encode(ENCODING)))
    if(public_key is not None):
        info['Encryption'] = f'key={Key_Encrypt(key)}'
    auth = b'admin:admin'
    info['Authorization: '] = 'Basic '+ base64.b64encode(auth).decode('utf-8')
    header = Generate_Req_Header(url, method, info)
    msg = header + CRLF + body
    return msg

def pow_Mod(x, y, Mod):
    res = 1
    while(y>0):
        if(y&1):
            res = res * x % Mod
        x = x * x % Mod
        y //= 2
    return res

key = 233
public_key = None
def Key_Encrypt(KEY):
    return pow_Mod(KEY,public_key[0],public_key[1])

def Encrypt(M):
    msg = b''
    for s in M:
        msg += 	((s + key) % 256).to_bytes()
    return msg

def Decrypt(M):
    msg = b''
    for s in M:
        msg += 	((s - key) % 256).to_bytes()
    return msg

try:
    cs.connect(addr)
    sendmsg = Generate_Req('/public_key.txt', 'GET', '')
    cs.send(sendmsg.encode(ENCODING))
    rcvmsg = cs.recv(1024)
    body = rcvmsg.split(b'\r\n\r\n')[1]
    public_key = int(body.split(b', ')[0]), int(body.split(b', ')[1])
    print(f'public_key:{public_key}')

    sendmsg = Generate_Req('/public_key.txt', 'GET', '')
    cs.send(sendmsg.encode(ENCODING))
    rcvmsg = cs.recv(1024)

    while True:
        msg = input('msg:') # Request content

        sendmsg = Generate_Req('/public_key.txt', 'GET',msg)
        cs.send(Encrypt(sendmsg.encode(ENCODING)))

        if(msg == 'quit'): # Exiting condition
            break


        rcvmsg = cs.recv(1024)
        print(b'Before Encryption:'+rcvmsg)
        rcvmsg = Decrypt(rcvmsg)
        print(rcvmsg)
        print(b'After Encryption:'+rcvmsg)

# except Exception as e:
    # print(e)
finally:
    cs.close()
    print('client closed')
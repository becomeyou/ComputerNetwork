import os

import base64

HOST, PORT = '0.0.0.0', 8080

ENCODING = 'utf-8'
CRLF = '\r\n'


def handlePost(conn, request,body, username, cookie=None):
    # 判断是否提供path
    query_params = parse_request(request)
    if 'path' not in query_params:
        return response_400(cookie)
    path_start = query_params.find('path=')
    this = query_params[path_start + 5:].split('/')[0]



    global content_type
    lines = request.split(CRLF)
    method = lines[0].split(' ')[0]
    url_start = lines[0].find(' ')
    url_end = lines[0].find(' ', url_start + 1)
    url = lines[0][url_start + 1:url_end]
    path_start = url.find('path=')
    path = url[path_start + 5:]
    path = 'data/' + path



    if method != 'POST':
        return response_405(cookie)
    if not os.path.exists(path):
        return response_404(cookie)
    if username != this:
        return response_403(cookie)



    # 删除
    if 'delete' in lines[0]:
        if handleDelete(conn, request):
            return response_200(cookie)

    for line in lines[1:]:
        if line.startswith('Content-Type'):
            content_type = line.split(': ')[1].strip()
            break
    
    boundary = '--' + content_type.split('; ')[1].split('=')[1].strip()
    data = body.split(boundary.encode())
    result = b''
    path = 'data/' + extract_path_id(lines[0])
    filename = ''

    
    
    for content in data:
        if(len(content) == 0 or content == b'--\r\n'):
            continue
        h,b = content.split(b'\r\n\r\n',1)
        if b'Content-Disposition' in h:
            content = h.split(CRLF.encode())[1].decode()
            filename = content.split('; ')[2].split('=')[1].strip('"').strip(CRLF)
        result += b
    # for i in range(1, len(data)):
    #     content = data[i]
    #     if 'Content-Disposition' in content:
    #         content = content.split(CRLF)
    #         filename = content[1].split('; ')[2].split('=')[1].strip('"').strip(CRLF)
    #         file_content = content[3:len(content) - 1]
    #         for line in range(len(file_content) - 1):
    #             result += file_content[line] + '\n'
    #         result += file_content[-1]
    #         path = 'data/' + extract_path_id(lines[0])

    save_file(filename, result, path)

    return response_200(cookie)


def save_file(filename, content, path):
    with open(os.path.join(path, filename), 'wb') as file:
        file.write(content)


def extract_path_id(first):
    url_start = first.find(' ')
    url_end = first.find(' ', url_start + 1)
    url = first[url_start + 1:url_end]
    path_start = url.find('path=')
    path = url[path_start + 5:]
    return path


def response_400(cookie):
    if cookie is not None:
        return f"HTTP/1.1 400 Bad Request\r\nSet-Cookie: session-id={cookie}\r\nContent-Length: 0\r\n\r\n400 Bad Request".encode()
    else:
        return f"HTTP/1.1 400 Bad Request\r\nContent-Length: 0\r\n\r\n400 Bad Request".encode()


def response_405(cookie):
    if cookie is not None:
        return f"HTTP/1.1 405 Method Not Allowed\r\nSet-Cookie: session-id={cookie}\r\nContent-Length: 0\r\n\r\n405 Method Not Allowed".encode()
    else:
        return f"HTTP/1.1 405 Method Not Allowed\r\nContent-Length: 0\r\n\r\n405 Method Not Allowed".encode()


def response_403(cookie):
    if cookie is not None:
        return f"HTTP/1.1 403 Forbidden\r\nSet-Cookie: session-id={cookie}\r\nContent-Length: 0\r\n\r\n403 Forbidden".encode()
    else:
        return f"HTTP/1.1 403 Forbidden\r\nContent-Length: 0\r\n\r\n403 Forbidden".encode()


def response_404(cookie):
    if cookie is not None:
        return f"HTTP/1.1 404 Not Found\r\nSet-Cookie: session-id={cookie}\r\nContent-Length: 0\r\n\r\n404 Not Found".encode()
    else:
        return f"HTTP/1.1 404 Not Found\r\nContent-Length: 0\r\n\r\n404 Not Found".encode()




def response_200(cookie):
    if cookie is not None:
        return f"HTTP/1.1 200 OK\r\nSet-Cookie: session-id={cookie}\r\nContent-Length: 0\r\n\r\n".encode()
    else:
        return f"HTTP/1.1 200 OK\r\nContent-Length: 0\r\n\r\n".encode()


def parse_request(request):
    lines = request.split('\r\n')
    first_line = lines[0]

    # 提取路径和查询参数
    path = first_line.split(' ')[1]


    return path


def handleDelete(conn, request):
    path = 'data/' + extract_path_id(request.split(CRLF)[0])

    try:
        os.remove(path)
        return True  # 文件删除成功
    except Exception as e:
        print(f"Error deleting file: {e}")
        return False  # 文件删除失败



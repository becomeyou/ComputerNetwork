import os
import uuid
import argparse
from threading import Thread
import json
import mimetypes
from socket import *
from pathlib import Path
from datetime import datetime


HOST, PORT = '0.0.0.0', 8080
ROOT_DIR = os.path.dirname(__file__)
DATA_DIR = os.path.join(os.path.dirname(__file__), 'data') 
BUFFER_SIZE = 4096
ENCODING = 'utf-8'
CRLF = '\r\n'

def url_encode(s):
    # 编码除了字母、数字、斜杠和几个特殊字符以外的所有字符
    return ''.join('%{:02X}'.format(ord(c)) if not c.isalnum() and c not in '-_.~/ ' else c for c in s)

def generate_directory_listing_html(path):
    # / and ../
    rela_root_path = os.path.relpath(path, ROOT_DIR).replace('\\', '/')
    relative_path = os.path.relpath(path, DATA_DIR).replace('\\', '/')
    parent_path = os.path.dirname(relative_path).replace('\\', '/')


    if(parent_path == ''):
        parent_path = '.'

    data_link = '<li><a href="/">/</a></li>'
    parent_link = '<li><a href="/{0}/">../</a></li>'.format(url_encode(parent_path))
    
    # 当前目录下的链接
    items = os.listdir(path)
    items_list = '\n'.join(
        f'<li><a href="/{url_encode(relative_path)}/{url_encode(item)}{"/" if os.path.isdir(os.path.join(path, item)) else ""}"{"" if os.path.isdir(os.path.join(path, item)) else " download"}>{item}{"/" if os.path.isdir(os.path.join(path, item)) else ""}</a></li>'
        for item in items
    )
    # items_list = '\n'.join(
    #     f'<li><a href="/{url_encode(relative_path)}/{url_encode(item)}{"/" if os.path.isdir(os.path.join(path, item)) else ""}">{item}{"/" if os.path.isdir(os.path.join(path, item)) else ""}</a></li>'
    #     for item in items
    # )
    
    html_content = f"""
<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 4.01//EN" "http://www.w3.org/TR/html4/strict.dtd">
<html>
<head>
<meta http-equiv="Content-Type" content="text/html; charset=utf-8">
<title>Directory listing for ./{rela_root_path}/</title>
</head>
<body>
<h1>Directory listing for ./{rela_root_path}/</h1>
<hr>
<ul>
{data_link}
{parent_link if relative_path != 'data' else '<li><a href="/data/">../</a></li>'}
{items_list}
</ul>
<hr>
</body>
</html>
"""
    return html_content

def parse_ranges(range_header, file_size):

    # 解析 Range 请求头，支持多个范围
    if range_header.startswith('bytes='):
        ranges = range_header[6:].split(',')
    else:
        ranges = range_header.split(',')

    result = []
    for part in ranges:
        start, sep, end = part.partition('-')
        if start == '':
            start = file_size - int(end)
            end = file_size - 1
        else:
            start = int(start)
            if end == '':
                end = file_size - 1
            else:
                end = int(end)
        if start > end or end >= file_size:
            return None
        result.append((start, end))
    return result

def create_multipart_content(file_path, ranges, file_size, boundary):
    content_type, _ = mimetypes.guess_type(file_path)
    content_type = content_type or 'application/octet-stream'
    multipart_content = b''

    if(len(ranges) == 1):
        with open(file_path, 'rb') as f:
            for start, end in ranges:
                f.seek(start)
                body = f.read(end - start + 1)

                multipart_content +=  body + b'\r\n'

        return multipart_content

    else:
        with open(file_path, 'rb') as f:
            for start, end in ranges:
                f.seek(start)
                body = f.read(end - start + 1)
                part_headers = (
                    f"--{boundary}\r\n"
                    f"Content-Type: {content_type}\r\n"
                    f"Content-Range: bytes {start}-{end}/{file_size}\r\n\r\n"
                )
                multipart_content += part_headers.encode() + body + b'\r\n'

        multipart_content += f"--{boundary}--".encode()
        return multipart_content

def response_200(body, content_type, cookie):
    if cookie is not None:
        return f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\nSet-Cookie: session-id={cookie}\r\n\r\n".encode()
    else:
        return f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\nContent-Length: {len(body)}\r\n\r\n".encode()

def response_200_chunked(client_socket,file_path, cookie):
    content_type, _ = mimetypes.guess_type(str(file_path))
    content_type = content_type or 'application/octet-stream'

    if cookie is not None:
        response_headers = f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\nTransfer-Encoding: chunked\r\nSet-Cookie: session-id={cookie}\r\n\r\n"
    else:
        response_headers = f"HTTP/1.1 200 OK\r\nContent-Type: {content_type}\r\nTransfer-Encoding: chunked\r\n\r\n"

    client_socket.sendall(response_headers.encode())

    # with open(file_path, 'rb') as f:
    #     while True:
    #         chunk = f.read(BUFFER_SIZE)
    #         if not chunk:
    #             break
            
    #         size_str = f"{len(chunk):X}\r\n"
    #         client_socket.sendall(size_str.encode() + chunk + b"\r\n")
    
    # client_socket.sendall(b"0\r\n\r\n")
    return

def response_206(client_socket,abs_path,range_header, cookie):
    file_size = os.path.getsize(abs_path)
    range_header = range_header.split('Range: ')[1]
    ranges = parse_ranges(range_header, file_size, cookie)

    if ranges is None:
        return response_416(client_socket, file_size ,cookie)
    
    content_type, _ = mimetypes.guess_type(str(abs_path))
    content_type = content_type or 'application/octet-stream'
    
    # 生成边界字符串
    boundary = uuid.uuid4().hex
    
    # 创建多部分内容
    multipart_content = create_multipart_content(abs_path, ranges, file_size, boundary)
    content_length = len(multipart_content)

    if len(ranges) == 1:
        start, end = ranges[0]
        if cookie is not None:
            response_headers = (
                f"HTTP/1.1 206 Partial Content\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Range: bytes {start}-{end}/{file_size}\r\n"
                f"Content-Length: {content_length}\r\n"
                f"Set-Cookie: session-id={cookie}\r\n\r\n"
            )
        else:
            response_headers = (
                f"HTTP/1.1 206 Partial Content\r\n"
                f"Content-Type: {content_type}\r\n"
                f"Content-Range: bytes {start}-{end}/{file_size}\r\n"
                f"Content-Length: {content_length}\r\n\r\n"
            )
    else:
        if cookie is not None:
            response_headers = (
                f"HTTP/1.1 206 Partial Content\r\n"
                f"Content-Type: multipart/byteranges; boundary={boundary}\r\n"
                f"Content-Length: {content_length}\r\n"
                f"Set-Cookie: session-id={cookie}\r\n\r\n"
            )
        else:
            response_headers = (
                f"HTTP/1.1 206 Partial Content\r\n"
                f"Content-Type: multipart/byteranges; boundary={boundary}\r\n"
                f"Content-Length: {content_length}\r\n\r\n"
            )
    client_socket.sendall(response_headers.encode())
    return

def response_400(cookie):
    if cookie is not None:
        return f"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\nContent-Length: 15\r\nSet-Cookie: session-id={cookie}\r\n\r\n".encode()
    else:
        return b"HTTP/1.1 400 Bad Request\r\nContent-Type: text/html\r\nContent-Length: 15\r\n\r\n"

def response_403(cookie):
    if cookie is not None:
        return f"HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\nContent-Length: 13\r\nSet-Cookie: session-id={cookie}\r\n\r\n".encode()
    else:
        return b"HTTP/1.1 403 Forbidden\r\nContent-Type: text/html\r\nContent-Length: 13\r\n\r\n"

def response_404(cookie):
    if cookie is not None:
        return f"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\nContent-Length: 13\r\nSet-Cookie: session-id={cookie}\r\n\r\n".encode()
    else:
        return b"HTTP/1.1 404 Not Found\r\nContent-Type: text/html\r\nContent-Length: 13\r\n\r\n"

def response_405(cookie):
    if cookie is not None:
        return f"HTTP/1.1 405 Method Not Allowed\r\nContent-Type: text/html\r\nContent-Length: 22\r\nSet-Cookie: session-id={cookie}\r\n\r\n"
    else:
        return b"HTTP/1.1 405 Method Not Allowed\r\nContent-Type: text/html\r\nContent-Length: 22\r\n\r\n"

def response_416(client_socket, file_size, cookie):

    if cookie is not None:
        response = (
            f"HTTP/1.1 416 Range Not Satisfiable\r\n"
            f"Content-Range: bytes */{file_size}\r\n"
            f"Content-Length: 25\r\n"
            f"Set-Cookie: session-id={cookie}\r\n"
        )
    else:
        response = (
            f"HTTP/1.1 416 Range Not Satisfiable\r\n"
            f"Content-Range: bytes */{file_size}\r\n"
            f"Content-Length: 25\r\n\r\n"
        )

    client_socket.sendall(response.encode())
    return 

def parse_query_string(query):
    query_params = {}
    for pair in query.split('&'):
        if '=' in pair:
            key, value = pair.split('=', 1)
            query_params[key] = value
    return query_params

def HandleHEAD(client_socket,request_data, cookie = None):
    # print("request_data", request_data)
    request_line = request_data.splitlines()[0].decode()

    # 检查是否有Range
    headers = request_data.decode().split('\r\n')
    range_header = next((header for header in headers if header.startswith('Range: ')), None)
    # print("range_header", range_header)

    method, full_path, _ = request_line.split()


    path, _, query = full_path.partition('?')
    query_params = parse_query_string(query)

    # unexpected query parameter
    for para in query_params:
        if(para != 'SUSTech-HTTP' and para != 'chunked'):
            return response_400(cookie)

    # paras
    sustech_http = query_params.get('SUSTech-HTTP', '0')
    chunked_transfer = query_params.get('chunked') == '1'

    path = path.lstrip('/')  # 移除开头的斜杠

    #abs_path = Path(os.path.join(ROOT_DIR, path))
    abs_path = Path(os.path.join(DATA_DIR, path))

    # exist
    if not abs_path.exists():
        return response_404(cookie)

    # dir
    if abs_path.is_dir():
        if sustech_http != '1' and sustech_http != '0':
            return response_400(cookie)
        if sustech_http == '1':
            items = os.listdir(abs_path)
            items_with_slash = [item + ("/" if os.path.isdir(os.path.join(abs_path, item)) else "") for item in items]
            response_body = json.dumps(items_with_slash).encode()
            return response_200(response_body, 'application/json', cookie)
        else:
            html_content = generate_directory_listing_html(abs_path)
            return response_200(html_content.encode(), 'text/html', cookie)

    # file
    elif abs_path.is_file():
        if chunked_transfer:
            response_200_chunked(client_socket,abs_path, cookie)
            return
        
        if range_header:
            response_206(client_socket,abs_path, range_header, cookie)
            return

        content_type, _ = mimetypes.guess_type(str(abs_path))
        content_type = content_type or 'application/octet-stream'

        file_size = os.path.getsize(abs_path)
        if file_size > BUFFER_SIZE:
            # print("big file, chunked transfer")
            return response_200_chunked(client_socket, abs_path, cookie)
        else:
            with open(abs_path, 'rb') as f:
                file_content = f.read()
            return response_200(file_content, content_type, cookie)

    # 如果既不是文件也不是目录，则返回404
    else:
        return response_404(cookie)
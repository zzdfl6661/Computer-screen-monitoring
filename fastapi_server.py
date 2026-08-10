import uvicorn
import argparse
from ssl_config import generate_self_signed_cert, get_ssl_context

def main():
    parser = argparse.ArgumentParser(description="智能劝学系统服务端")
    parser.add_argument('--host', type=str, default='0.0.0.0', help='服务绑定地址')
    parser.add_argument('--port', type=int, default=5000, help='服务端口')
    parser.add_argument('--ssl', action='store_true', help='启用 HTTPS')
    parser.add_argument('--cert', type=str, default=None, help='SSL 证书文件路径')
    parser.add_argument('--key', type=str, default=None, help='SSL 密钥文件路径')
    parser.add_argument('--reload', action='store_true', help='开发模式自动重载')
    
    args = parser.parse_args()
    
    if args.ssl:
        cert_path, key_path = generate_self_signed_cert(args.cert, args.key)
        ssl_context = get_ssl_context(cert_path, key_path)
        
        print(f"服务启动: https://{args.host}:{args.port}")
        print(f"SSL 证书: {cert_path}")
        print(f"SSL 密钥: {key_path}")
        
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            ssl_context=ssl_context,
            reload=args.reload
        )
    else:
        print(f"服务启动: http://{args.host}:{args.port}")
        print("警告: 未启用 SSL，建议在生产环境中使用 --ssl 参数")
        
        uvicorn.run(
            "app.main:app",
            host=args.host,
            port=args.port,
            reload=args.reload
        )

if __name__ == "__main__":
    main()
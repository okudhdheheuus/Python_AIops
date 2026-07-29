
import asyncssh
from ..models import Server
class SSHService:
    @staticmethod
    async def test_connection(server: Server) -> dict:
        """测试SSH连接是否正常"""
        try:
            conn = await asyncssh.connect(
                host=server.host,
                port=server.port,
                username=server.username,
                password=server.password if not server.use_ssh_key else None,
                client_keys=[server.private_key] if server.use_ssh_key and server.private_key else None,
                known_hosts=None
            )
            result = await conn.run("echo 'SSH connection successful'",check=False)
            conn.close()
            return{
                "success":True,
                "stdout":result.stdout,
                "stderr":result.stderr,
                "exit_code": result.exit_status
            }
        except Exception as e:
            return {
                "success": False,
                "error": str(e)
            }

    @staticmethod
    async def execute_command(server: Server,command:str) -> dict:
        """在远程服务器执行命令"""
        try:
            conn = await asyncssh.connect(
                host=server.host,
                port=server.port,
                username=server.username,
                password = server.password if not server.use_ssh_key else None,
                client_keys = [server.private_key] if server.use_ssh_key and server.private_key else None,
                known_hosts=None
            )
            result = await conn.run(command,check=False)
            conn.close()
            return {
                "success": result.exit_status == 0,
                "stdout": result.stdout,
                "stderr": result.stderr,
                "exit_code": result.exit_status
            }
        except Exception as e:
            return {"success":False,"error":str(e)}

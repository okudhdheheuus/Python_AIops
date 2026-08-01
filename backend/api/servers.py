import csv
import io

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile
from fastapi.responses import StreamingResponse
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from ..database import get_db
from ..models import Server, User
from ..schemas import ServerCreate, ServerOut, ServerUpdate
from ..services.audit_service import log_audit
from ..services.ssh_service import SSHService
from ..utils.security import get_current_active_user

router = APIRouter()

def _server_ownership_filter(stmt, current_user: User):
    """每个用户只能看到自己的服务器"""
    stmt = stmt.where(Server.owner_id == current_user.id)
    return stmt

async def _require_server_ownership(server_id: str, db: AsyncSession, current_user: User) -> Server:
    """获取服务器并校验所有权（每个用户只能操作自己的）"""
    server = await db.get(Server, server_id)
    if not server:
        raise HTTPException(status_code=404, detail="Server not found")
    if server.owner_id != current_user.id:
        raise HTTPException(status_code=404, detail="Server not found")
    return server

# 创建服务器
@router.post("/servers",response_model=ServerOut,status_code=201)
async def create_server(
    server_in: ServerCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    new_server = Server(**server_in.model_dump(), owner_id=current_user.id)
    db.add(new_server)
    await db.commit()
    await db.refresh(new_server)
    await log_audit(
        username=current_user.username,
        action=f"创建服务器 {new_server.name}({new_server.host})",
        resource_type="server",
        resource_id=new_server.id,
    )
    return ServerOut.model_validate(new_server)

# 获取所有服务器
@router.get("/servers",response_model=list[ServerOut])
async def list_servers(
    df: AsyncSession = Depends(get_db),
    skip: int = 0,
    limit: int = Query(default=100, le=500),
    tag: str | None = None,
    current_user: User = Depends(get_current_active_user)
):
    stmt = select(Server).order_by(Server.name)
    stmt = _server_ownership_filter(stmt, current_user)
    if tag:
        stmt = stmt.where(Server.tags.contains(tag))
    stmt = stmt.offset(skip).limit(limit)
    result = await df.execute(stmt)
    servers = result.scalars().all()
    return [ServerOut.model_validate(s) for s in servers]

# 导出服务器为CSV —— 必须在 /{server_id} 之前注册，避免路由冲突
@router.api_route("/servers/export-csv", methods=["GET", "POST"])
async def export_servers_csv(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """导出服务器列表为CSV"""
    async def generate_csv():
        yield "name,host,port,username,tags,enabled,description\n"
        stmt = _server_ownership_filter(select(Server).order_by(Server.name), current_user)
        stream = await db.stream(stmt)
        try:
            async for server in stream.scalars():
                row = [
                    server.name or "",
                    server.host or "",
                    server.port or 22,
                    server.username or "",
                    server.tags or "",
                    "true" if server.enabled else "false",
                    server.description or "",
                ]
                output = io.StringIO()
                writer = csv.writer(output, lineterminator="\n")
                writer.writerow(row)
                yield output.getvalue()
        finally:
            await stream.close()

    return StreamingResponse(
        generate_csv(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment;filename=servers.csv"}
    )

# 获取单个服务器
@router.get("/servers/{server_id}",response_model=ServerOut)
async def get_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    server = await _require_server_ownership(server_id, db, current_user)
    return ServerOut.model_validate(server)

# 更新服务器
@router.put("/servers/{server_id}",response_model=ServerOut)
async def update_server(
    server_id: str,
    server_in: ServerUpdate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    server = await _require_server_ownership(server_id, db, current_user)
    for field,value in server_in.model_dump(exclude_unset=True).items():
        setattr(server,field,value)
    await db.commit()
    await db.refresh(server)
    await log_audit(
        username=current_user.username,
        action=f"更新服务器 {server.name}({server.host})",
        resource_type="server",
        resource_id=server.id,
    )
    return ServerOut.model_validate(server)

# 删除服务器
@router.delete("/servers/{server_id}",status_code=204)
async def delete_server(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    server = await _require_server_ownership(server_id, db, current_user)
    await db.delete(server)
    await db.commit()
    await log_audit(
        username=current_user.username,
        action=f"删除服务器 {server.name}({server.host})",
        resource_type="server",
        resource_id=server.id,
    )
    return {"detail":"server deleted successfully"}

# 测试服务器连接
@router.post("/servers/{server_id}/test-connection")
async def test_server_connection(
    server_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    server = await _require_server_ownership(server_id, db, current_user)
    result = await SSHService.test_connection(server)
    return result

@router.post("/servers/import-csv",status_code=201)
async def import_servers_csv(
    file: UploadFile = File(...),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_active_user)
):
    """CSV 批量导入服务器"""
    if current_user.role not in ["admin","operator"]:
        raise HTTPException(status_code=403,detail="Not enough permission")
    content = await file.read()
    try:
        text = content.decode("utf-8-sig") # 处理BOM头
    except UnicodeDecodeError:
        text = content.decode("gbk")
    reader = csv.DictReader(io.StringIO(text))

    imported=0
    errors=[]
    try:
        for row_num,row in enumerate(reader,start=2): # 从第二行开始(跳过表头)
            if not row or not any((value or "").strip() for value in row.values()):
                continue

            name = (row.get("name") or "").strip()
            host = (row.get("host") or "").strip()
            if not name or not host:
                errors.append(f"第{row_num}行，名称或主机为空")
                continue

            existing = await db.execute(
                select(Server).where(Server.name == name, Server.host == host)
            )
            if existing.scalar_one_or_none():
                errors.append(f"第{row_num}行:服务器{name}({host}) 已存在")
                continue

            server = Server(
                name=name,
                host=host,
                port=int(row.get("port") or 22),
                username=row.get("username") or "root",
                password=row.get("password") or None,
                description=row.get("description") or None,
                tags=row.get("tags") or None,
                owner_id=current_user.id,
            )
            db.add(server)
            imported += 1

        await db.commit()
    except Exception:
        await db.rollback()
        raise

    return {"imported":imported,"errors":errors}


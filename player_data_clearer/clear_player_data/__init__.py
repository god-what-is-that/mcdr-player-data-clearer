from mcdreforged.api.all import *
from pathlib import Path
import yaml
import shutil
import os
import requests


# 初始化配置
def copyFile(path, target_path, server):            
    if os.path.exists(target_path):
        return
    target_path = Path(target_path)
    target_path.parent.mkdir(parents=True, exist_ok=True)
    with server.open_bundled_file(path) as file_handler: # 从包内解包文件
        message = file_handler.read()
    with open(target_path, 'wb') as f:                        # 复制文件
        f.write(message)


# 全局变量
config = None


def delete_player_data(server: ServerInterface, uuid: str, config) -> bool:
    """删除指定UUID的玩家数据文件"""

    def start_delete(suffix, one_path):

        # 构建文件路径
        if suffix == "file":
            playerdata_path = os.path.join(server.get_mcdr_config()['working_directory'],config["world_dir"],config[suffix][one_path],uuid)
        else:
            playerdata_path = os.path.join(server.get_mcdr_config()['working_directory'],config["world_dir"],config[suffix][one_path],f'{uuid}.{suffix}')

        # 检查文件是否存在
        if os.path.isfile(playerdata_path):

            # 尝试删除文件
            try:
                os.remove(playerdata_path)
                server.logger.info(f"成功删除玩家数据文件: {playerdata_path}")
                return True
            except Exception as e:
                server.logger.error(f"删除玩家数据文件失败: {e}")
                return False

        elif os.path.exists(playerdata_path):
            
            # 尝试删除文件
            try:
                shutil.rmtree(playerdata_path)
                server.logger.info(f"成功删除玩家数据文件: {playerdata_path}")
                return True
            except Exception as e:
                server.logger.error(f"删除玩家数据文件失败: {e}")
                return False
            
        else:
            server.logger.info(f"玩家数据文件不存在: {playerdata_path}")
            return True
        
    # 遍历所有文件
    for suffix, data_path in config.items():
        if type(data_path) == dict and suffix != "command":
            for one_path in data_path:
                if not start_delete(suffix, one_path):
                    return False
    
    return True


def on_load(server: ServerInterface, old_module):
    """插件加载时调用"""

    copyFile("clear_player_data/data/config_default.yml", "./config/clear_player_data/config.yml", server)

    def load_config() -> dict:
        config_path = Path("./config/clear_player_data/config.yml")
        with open(config_path, 'r', encoding='utf-8') as f:
            return yaml.safe_load(f)

    # 加载配置
    global config
    config = load_config()

    # 注册命令
    server.register_command(
        Literal('!!cpd')
        # 分支1: !!cpd uuid <value> → 触发 handle_command
        .then(
            Literal('uuid')
            .then(Text('uuid_value').runs(lambda src, ctx: handle_command(src, ctx['uuid_value'], config)))
        )
        # 分支2: !!cpd playerid <value> → 触发 handle_command2
        .then(
            Literal('playerid')
            .then(Text('playerid_value').runs(lambda src, ctx: handle_command2(src, ctx['playerid_value'], config)))
        )
        # 分支3: !!cpd clean <value> → 触发 handle_command3
        .then(
            Literal('clean')
            .then(
                Integer('day_value')
                .runs(lambda src, ctx: src.reply(
                    f"请确认清理 {ctx['day_value']} 天前的数据，输入: "
                    f"!!cpd clean {ctx['day_value']} confirm"
                ))
                .then(
                    Literal('confirm')
                    .runs(lambda src, ctx: handle_command3(src, ctx['day_value'], config)))
            )
        )
    )

    # 注册帮助信息
    server.register_help_message('!!cpd uuid <uuid>', '清除指定UUID的玩家数据')
    server.register_help_message('!!cpd playerid <playerid>', '清除指定玩家数据')
    server.register_help_message('!!cpd clean <day>', '清除多少天未修改的玩家数据')


# 检查服务器是否开启了正版验证
def get_online_mode(server) -> bool:
    """
    读取 server.properties 中的 online-mode 值
    返回 bool 类型（True=正版验证，False=离线模式）
    """
    # 获取 server.properties 的完整路径
    props_path = os.path.join(server.get_mcdr_config()['working_directory'],"server.properties")
    
    try:
        with open(props_path, 'r', encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line.startswith('online-mode='):
                    value = line.split('=')[1].strip().lower()
                    return value == 'true'
    except FileNotFoundError:
        server.logger.error("server.properties 文件未找到！")
    except Exception as e:
        server.logger.error(f"读取 server.properties 失败: {e}")
    
    # 默认返回 True（安全值，兼容正版服务器）
    return True


# 通过playerid获取uuid
def get_uuid(playerid, server):

    # 调用官方api获取正版uuid
    def online_uuid(name, online_api):

        # 尝试访问网址5次
        def get_try(url):
            for i in range(0, 5):
                try:
                    return requests.get(url).json()
                except:
                    pass
            return None
        
        url = f'{online_api}{name}'
        r = get_try(url)
        if r is None:
            return None
        else:
            return r['id']

    # 自己算离线uuid
    def offline_uuid(name):

        import uuid, hashlib

        def get_offline_uuid(username: str) -> str:
            # 构造字符串，加前缀
            name = "OfflinePlayer:" + username
            # MD5 摘要
            md5 = hashlib.md5(name.encode('utf-8')).digest()
            # 修改版本和 variant 字节
            ba = bytearray(md5)
            ba[6] = (ba[6] & 0x0F) | 0x30  # 设置为 version 3
            ba[8] = (ba[8] & 0x3F) | 0x80  # 设置为 IETF variant
            # 构建 UUID 对象
            generated_uuid = uuid.UUID(bytes=bytes(ba))
            return str(generated_uuid)
        
        return get_offline_uuid(name)


    if get_online_mode(server):
        return online_uuid(playerid, "https://api.mojang.com/users/profiles/minecraft/")
    else:
        return offline_uuid(playerid)



# !!cpd uuid 时执行此函数
def handle_command(source: CommandSource, uuid: str, config):
    """处理命令请求"""

    # 检查权限
    if source.has_permission(4):  # OP权限

        # 执行config中的命令
        if config["command"]["uuid"] and config["command"]["uuid"] != {}:
            for command in config["command"]["uuid"]:
                command = config["command"]["playerid"][command]
                source.get_server().execute(command.replace("<uuid>", uuid))

        source.get_server().logger.info(f"收到清除玩家数据请求: UUID={uuid}")

        if delete_player_data(source.get_server(), uuid, config):
            source.reply(f"§a成功清除UUID为 {uuid} 的玩家数据或玩家数据不存在")
        else:
            source.reply(f"§c清除玩家数据失败，请检查控制台日志获取详细信息")
        
    else:
        source.reply("§c你没有权限执行此命令")


# !!cpd playerid 时执行此函数
def handle_command2(source: CommandSource, playerid: str, config):

    # 检查权限
    if source.has_permission(4):  # OP权限

        # 执行config中的命令
        if config["command"]["playerid"] and config["command"]["playerid"] != {}:
            for command in config["command"]["playerid"]:
                command = config["command"]["playerid"][command]
                source.get_server().execute(command.replace("<playerid>", playerid))
        
        uuid = get_uuid(playerid, source.get_server())

        handle_command(source, uuid, config)

    else:
        source.reply("§c你没有权限执行此命令")


# !!cpd clean 时执行此函数
def handle_command3(source: CommandSource, day: int, config):
    
    # 检查权限
    if source.has_permission(4):  # OP权限
        
        import time
        from typing import List, Set

        server = source.get_server()

        def get_old_playerdata_files(server, config, days_threshold: int) -> List[str]:

            # 计算时间阈值（当前时间 - days_threshold天）
            threshold_time = time.time() - days_threshold * 86400  # 86400秒=1天
            
            # 构建playerdata目录路径
            dat_path = os.path.join(
                server.get_mcdr_config()['working_directory'],
                config["world_dir"],
                "playerdata1"
            )
            
            unique_files: Set[str] = set()  # 用于去重的集合
            
            try:
                # 遍历目录中的所有文件
                for filename in os.listdir(dat_path):
                    filepath = os.path.join(dat_path, filename)
                    
                    # 跳过目录和非文件项
                    if not os.path.isfile(filepath):
                        continue
                        
                    # 检查文件修改时间
                    mtime = os.path.getmtime(filepath)
                    if mtime < threshold_time:
                        # 去除文件后缀并添加到集合中
                        filename_no_ext = Path(filename).stem
                        unique_files.add(filename_no_ext)
                        
            except FileNotFoundError:
                server.logger.warning(f"playerdata目录不存在: {dat_path}")
                return []
            except Exception as e:
                server.logger.error(f"遍历playerdata目录出错: {str(e)}")
                return []
            
            return list(unique_files)  # 转换为列表返回

        uuids = get_old_playerdata_files(server, config, day)
        if uuids == []:
            source.reply(f"§c没有天{day}内未修改的玩家存档，或是获取失败，请查看控制台日志获取详细信息")
            return
        for uuid in uuids:
            handle_command(source, uuid, config)
        
        

    else:
        source.reply("§c你没有权限执行此命令")

import time
from hoshino.typing import CQEvent
from hoshino.modules.priconne._pcr_data import CHARA_NAME
from ..clanbattle import clanbattle_info
from ..clanbattle.model import ClanBattle


# 场景英文名 - 别名
SCENE_ALIAS_GROUPS = {
    'dungeon': ['地下城'],
    'clan_battle': ['公会', '工会', '工会战', '公会战', '会战'],
    'luna_tower': ['露娜', '露娜塔'],
    'friend': ['关卡', '活动', '深域', '深渊'],
}
# 展开为扁平字典：别名 - 场景英文名
SCENE_ALIAS = {
    alias: scene_name
    for scene_name, aliases in SCENE_ALIAS_GROUPS.items()
    for alias in aliases
}

# 场景 - 更换助战所需的所有参数
SCENE_CONFIG = {
    'dungeon': {
        'display_name': '地下城',
        'support_type': 1,       # 助战位类型: 1=地下城&会战
        'position_offset': 1,    # 位置偏移: 占用位置1-2
        'units_key': 'dungeon'   # 助战位标准名
    },
    'clan_battle': {
        'display_name': '公会战',
        'support_type': 1,
        'position_offset': 3,    # 位置偏移: 占用位置3-4
        'units_key': 'clan'
    },
    'luna_tower': {
        'display_name': '露娜塔',
        'support_type': 1,
        'position_offset': 3,    # 位置偏移: 占用位置3-4（与公会战共用）
        'units_key': 'clan'
    },
    'friend': {
        'display_name': '关卡&活动',
        'support_type': 2,       # API类型: 2=好友系统
        'position_offset': 1,
        'units_key': 'friend'
    }
}

# 公会战相关场景
CLAN_BATTLE_SCENES = {'公会战', '会战', '工会战', '工会', '公会'}

# 助战位冷却时间（秒）
COOLDOWN_TIME = 1800  # 30分钟


def get_scene_config(scene: str) -> dict:
    """根据场景名称获取配置"""
    standard_scene = SCENE_ALIAS.get(scene, 'clan_battle')
    return SCENE_CONFIG[standard_scene]


def find_character_by_name(target_name: str) -> tuple:
    """根据角色名或外号查找角色ID和正式名称
    
    Args:
        target_name: 目标角色名或外号
        
    Returns:
        (chara_id, chara_name) 如果找到，否则 (0, None)
    """
    for chara_id, names in CHARA_NAME.items():
        if target_name in names:
            return chara_id, names[0]
    return 0, None


def get_qq_id(ev: CQEvent, scene: str, group_id: int) -> tuple:
    """获取目标用户的QQ号
    
    Args:
        ev: 事件对象
        scene: 场景名称
        group_id: 群组ID
        
    Returns:
        (qq_id, error_message) 如果成功返回 (qq_id, None)，失败返回 (0, error_message)
    """
    is_at = len(ev.message) == 3 and ev.message[0].type == 'text' and ev.message[1].type == 'at'
    
    if is_at:
        try:
            qq_id = int(ev.message[1].data['qq'])
            return qq_id, None
        except (KeyError, ValueError, TypeError):
            return 0, '无法解析@的用户信息'
    
    if scene in CLAN_BATTLE_SCENES:
        # 检查群是否有公会信息
        if group_id not in clanbattle_info:
            return 0, '本群暂未有人开启出刀监控，请先发送“出刀监控”或直接@目标用户'
        
        clan_info: ClanBattle = clanbattle_info[group_id]
        
        # 检查是否设置了助战人QQ
        if not hasattr(clan_info, 'qq_id') or not clan_info.qq_id:
            return 0, '本群暂未有人开启出刀监控，请先发送“出刀监控”或直接@目标用户'
        
        return clan_info.qq_id, None
    
    return ev.user_id, None


def parse_support_units(clan_dungeon_units: list, friend_units_data: list) -> dict:
    """解析助战单位数据到结构化字典
    
    Args:
        clan_dungeon_units: 公会和地下城助战单位列表
        friend_units_data: 好友助战单位列表
        
    Returns:
        包含三种类型助战单位的字典
    """
    default_unit = {'unit_id': 100000, 'support_start_time': 0, 'clan_support_count': 0}
    # 由于pcr无助战的位置不会在接口返回值中，因此需要先构建一个骨架，然后将对应的接口返回值覆盖上去
    units = {
        'dungeon': [dict(default_unit, position=1, clan_support_count=1), dict(default_unit, position=2)],
        'clan': [dict(default_unit, position=3, clan_support_count=1), dict(default_unit, position=4)],
        'friend': [dict(default_unit, position=1, clan_support_count=1), dict(default_unit, position=2)]
    }
    
    for unit in clan_dungeon_units:
        pos = unit['position']
        if pos in (1, 2):
            units['dungeon'][pos - 1] = unit
        elif pos in (3, 4):
            units['clan'][pos - 3] = unit
    
    for unit in friend_units_data:
        pos = unit['position']
        if pos in (1, 2):
            units['friend'][pos - 1] = unit
    
    return units


def check_character_in_support(all_units: list, chara_id: int) -> tuple:
    """检查角色是否已在助战中
    
    Args:
        all_units: 所有助战单位列表
        chara_id: 角色ID
        
    Returns:
        (is_in_support, position_name, support_type, position) 
        是否在助战中、所在位置名称、助战类型、位置编号
    """
    for unit in all_units:
        unit_id = int(str(unit['unit_id'])[:-2])
        if chara_id == unit_id:
            position = unit['position']
            if 'friend_support_reward' in unit:
                return True, "关卡&活动", 2, position
            elif position in (1, 2):
                return True, "地下城", 1, position
            else:
                return True, "公会&露娜塔", 1, position
    return False, None, None, None


async def change_support_unit(client, support_type: int, position: int, unit_id: int) -> bool:
    """更换助战角色
    
    Args:
        client: API客户端
        support_type: 助战类型
        position: 位置
        unit_id: 角色单位ID
        
    Returns:
        是否成功
    """
    try:
        await client.callapi('/support_unit/change_setting', {
            'support_type': support_type,
            'position': position,
            'action': 2,
            'unit_id': unit_id
        })
        time.sleep(3)
        await client.callapi('/support_unit/change_setting', {
            'support_type': support_type,
            'position': position,
            'action': 1,
            'unit_id': unit_id
        })
        return True
    except Exception:
        return False


async def remove_support_unit(client, support_type: int, position: int) -> bool:
    """取下助战角色
    
    Args:
        client: API客户端
        support_type: 助战类型
        position: 位置
        
    Returns:
        是否成功
    """
    try:
        await client.callapi('/support_unit/change_setting', {
            'support_type': support_type,
            'position': position,
            'action': 2,
            'unit_id': 0
        })
        time.sleep(3)
        return True
    except Exception:
        return False

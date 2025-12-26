"""
SQLite 数据库管理器 (SQL Store)
负责管理单项目目录下的 content.db。
"""
import os
import logging
import json
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from core.models import Base, ProjectSetting, Chapter, TimelineEvent
from functools import lru_cache

logger = logging.getLogger(__name__)

@lru_cache(maxsize=5)
def get_engine(project_root: str):
    """
    获取指定项目的数据库引擎 (带缓存)。
    """
    db_path = os.path.join(project_root, "content.db")
    # 使用 check_same_thread=False 允许 Streamlit 多线程访问
    engine = create_engine(f"sqlite:///{db_path}", connect_args={"check_same_thread": False})
    
    # 自动建表
    Base.metadata.create_all(engine)
    return engine

def get_session(project_root: str) -> Session:
    """获取一个新的数据库会话"""
    engine = get_engine(project_root)
    SessionLocal = sessionmaker(bind=engine)
    return SessionLocal()

# --- 具体的 CRUD 操作 ---

def save_setting(project_root: str, key: str, value: str):
    """保存或更新全局设置"""
    session = get_session(project_root)
    try:
        setting = session.query(ProjectSetting).filter_by(key=key).first()
        if setting:
            setting.value = value
        else:
            setting = ProjectSetting(key=key, value=value)
            session.add(setting)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"保存设置失败 {key}: {e}")
    finally:
        session.close()

def get_setting(project_root: str, key: str, default: str = "") -> str:
    """读取全局设置"""
    session = get_session(project_root)
    try:
        setting = session.query(ProjectSetting).filter_by(key=key).first()
        return setting.value if setting else default
    finally:
        session.close()

def save_chapter(project_root: str, index: int, content: str, title: str = None):
    """保存章节"""
    session = get_session(project_root)
    try:
        chapter = session.query(Chapter).filter_by(index=index).first()
        if chapter:
            chapter.content = content
            chapter.word_count = len(content)
            if title: chapter.title = title
        else:
            chapter = Chapter(index=index, content=content, word_count=len(content), title=title)
            session.add(chapter)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"保存章节失败 {index}: {e}")
    finally:
        session.close()

def get_all_chapters(project_root: str):
    """获取所有章节，按顺序排列"""
    session = get_session(project_root)
    try:
        chapters = session.query(Chapter).order_by(Chapter.index).all()
        return [{"index": c.index, "content": c.content, "title": c.title, "word_count": c.word_count} for c in chapters]
    finally:
        session.close()

def get_chapter_count(project_root: str) -> int:
    session = get_session(project_root)
    try:
        return session.query(Chapter).count()
    finally:
        session.close()

def save_timeline_event(project_root: str, event_data: dict):
    """保存或更新时间轴事件"""
    session = get_session(project_root)
    try:
        idx = event_data.get("chapter_index")
        existing = session.query(TimelineEvent).filter_by(chapter_index=idx).first()
        if existing:
            existing.time_str = event_data.get("time")
            existing.location = event_data.get("location")
            existing.tension = event_data.get("tension", 5.0)
            existing.word_count = event_data.get("word_count", 0)
            existing.event_desc = event_data.get("summary")
        else:
            new_event = TimelineEvent(
                chapter_index=idx,
                time_str=event_data.get("time"),
                location=event_data.get("location"),
                tension=event_data.get("tension", 5.0),
                word_count=event_data.get("word_count", 0),
                event_desc=event_data.get("summary")
            )
            session.add(new_event)
        session.commit()
    except Exception as e:
        session.rollback()
        logger.error(f"保存时间轴事件失败: {e}")
    finally:
        session.close()

def get_timeline(project_root: str):
    """获取项目完整时间轴数据"""
    session = get_session(project_root)
    try:
        events = session.query(TimelineEvent).order_by(TimelineEvent.chapter_index).all()
        return [
            {
                "chapter_index": e.chapter_index,
                "time": e.time_str,
                "location": e.location,
                "tension": e.tension,
                "word_count": e.word_count,
                "summary": e.event_desc
            } for e in events
        ]
    finally:
        session.close()


# --- 状态与 SQL 同步高级操作 ---

def save_project_state_to_sql(project_root: str, state_dict: dict):
    """
    将 Session State 中的关键数据同步到 SQL。
    """
    session = get_session(project_root)
    try:
        for k, v in state_dict.items():
            if v is None: continue
            
            # 特殊处理章节列表：存入 chapters 表
            if k == 'drafts' and isinstance(v, list):
                for idx, content in enumerate(v):
                    if not content: continue
                    ch = session.query(Chapter).filter_by(index=idx+1).first()
                    if ch:
                        ch.content = content
                        ch.word_count = len(content)
                    else:
                        session.add(Chapter(index=idx+1, content=content, word_count=len(content)))
            
            # 其他字段存入设置表
            elif isinstance(v, (str, int, float, bool)):
                setting = session.query(ProjectSetting).filter_by(key=k).first()
                val_str = str(v) if not isinstance(v, str) else v
                if setting:
                    setting.value = val_str
                else:
                    session.add(ProjectSetting(key=k, value=val_str))
            
            # 复杂对象（List/Dict）序列化为 JSON 存储
            elif isinstance(v, (list, dict)):
                val_str = json.dumps(v, ensure_ascii=False)
                setting = session.query(ProjectSetting).filter_by(key=k).first()
                if setting:
                    setting.value = val_str
                else:
                    session.add(ProjectSetting(key=k, value=val_str))
        
        session.commit()
        return True
    except Exception as e:
        session.rollback()
        logger.error(f"同步状态至 SQL 失败: {e}")
        return False
    finally:
        session.close()

def load_project_state_from_sql(project_root: str) -> dict:
    """
    从 SQL 加载项目数据还原为 State 字典。
    """
    session = get_session(project_root)
    state_data = {}
    try:
        # 1. 加载设置
        settings = session.query(ProjectSetting).all()
        for s in settings:
            try:
                # 尝试解析 JSON (针对列表或字典字段)
                state_data[s.key] = json.loads(s.value)
            except:
                state_data[s.key] = s.value
        
        # 2. 加载章节 (还原 drafts 列表)
        chapters = session.query(Chapter).order_by(Chapter.index).all()
        if chapters:
            state_data['drafts'] = [c.content for c in chapters]
            # 这里的 index 是关键，必须反映真实的撰写进度
            state_data['drafting_index'] = len(chapters)
        else:
            state_data['drafts'] = []
            state_data['drafting_index'] = 0
            
        return state_data
    except Exception as e:
        logger.error(f"从 SQL 加载状态失败: {e}")
        return {}
    finally:
        session.close()


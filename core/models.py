"""
核心数据模型 (Data Models)
定义存储在 SQLite (content.db) 中的表结构。
"""
from sqlalchemy import Column, Integer, String, Text, Float, create_engine
from sqlalchemy.orm import declarative_base

Base = declarative_base()

class ProjectSetting(Base):
    """
    项目全局设置表 (Key-Value)
    用于存储 plan, outline, world_bible, research_results 等非结构化大文本。
    """
    __tablename__ = 'project_settings'
    
    key = Column(String, primary_key=True)
    value = Column(Text, nullable=True)

class Chapter(Base):
    """
    章节表
    存储正文、摘要及基础元数据。
    """
    __tablename__ = 'chapters'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    index = Column(Integer, unique=True, nullable=False) # 第几章
    title = Column(String, nullable=True) # 章节标题
    content = Column(Text, nullable=True) # 正文
    summary = Column(Text, nullable=True) # 摘要
    word_count = Column(Integer, default=0) # 字数

class TimelineEvent(Base):
    """
    时间轴事件表 (用于剧情洞察)
    """
    __tablename__ = 'timeline_events'
    
    id = Column(Integer, primary_key=True, autoincrement=True)
    chapter_index = Column(Integer, nullable=False)
    time_str = Column(String, nullable=True) # 故事内时间，如 "1990年"
    location = Column(String, nullable=True)
    tension = Column(Float, default=0.0) # 戏剧张力 (1-10)
    event_desc = Column(String, nullable=True) # 简短事件描述

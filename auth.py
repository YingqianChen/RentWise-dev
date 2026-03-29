"""用户认证模块"""

import re
from datetime import datetime, timedelta
from typing import Optional, Tuple

import bcrypt
from jose import JWTError, jwt

from config import settings
from database import init_db, get_db_session
from repository import UserRepository
from models import User

# JWT配置（从配置模块读取）
SECRET_KEY = settings.SECRET_KEY
ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_DAYS = 7


def init_auth():
    """初始化认证系统（创建数据库表）"""
    init_db()


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """验证密码"""
    return bcrypt.checkpw(plain_password.encode('utf-8'), hashed_password.encode('utf-8'))


def hash_password(password: str) -> str:
    """哈希密码"""
    return bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None) -> str:
    """创建JWT访问令牌"""
    to_encode = data.copy()
    expire = datetime.utcnow() + (expires_delta or timedelta(days=ACCESS_TOKEN_EXPIRE_DAYS))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)


def verify_token(token: str) -> Optional[str]:
    """验证JWT令牌，返回用户ID或None"""
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            return None
        return user_id
    except JWTError:
        return None


def validate_email(email: str) -> bool:
    """验证邮箱格式"""
    pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    return re.match(pattern, email) is not None


def validate_password(password: str) -> Tuple[bool, str]:
    """
    验证密码强度

    Returns:
        (是否有效, 错误信息)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    if not re.search(r'[A-Za-z]', password):
        return False, "Password must contain at least one letter"
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    return True, ""


class AuthService:
    """认证服务类"""

    def __init__(self):
        self.repo = UserRepository()

    def register(self, email: str, password: str) -> Tuple[Optional[User], str]:
        """
        用户注册

        Returns:
            (用户对象, 错误信息)
        """
        # 验证邮箱
        if not validate_email(email):
            return None, "Invalid email format"

        # 验证密码
        valid, error = validate_password(password)
        if not valid:
            return None, error

        # 检查邮箱是否已存在
        existing = self.repo.get_user_by_email(email)
        if existing:
            return None, "Email already registered"

        # 创建用户
        password_hash = hash_password(password)
        try:
            user = self.repo.create_user(email, password_hash)
            return user, ""
        except Exception as e:
            return None, f"Registration failed: {str(e)}"

    def login(self, email: str, password: str) -> Tuple[Optional[str], str]:
        """
        用户登录

        Returns:
            (JWT令牌, 错误信息)
        """
        # 查找用户
        user = self.repo.get_user_by_email(email)
        if not user:
            return None, "Invalid email or password"

        # 验证密码
        if not verify_password(password, user.password_hash):
            return None, "Invalid email or password"

        # 更新登录时间
        self.repo.update_last_login(user.id)

        # 创建令牌
        token = create_access_token(data={"sub": user.id})
        return token, ""

    def get_current_user(self, token: str) -> Optional[User]:
        """通过令牌获取当前用户"""
        user_id = verify_token(token)
        if not user_id:
            return None
        return self.repo.get_user_by_id(user_id)

    def change_password(
        self, user_id: str, old_password: str, new_password: str
    ) -> Tuple[bool, str]:
        """修改密码"""
        user = self.repo.get_user_by_id(user_id)
        if not user:
            return False, "User not found"

        # 验证旧密码
        if not verify_password(old_password, user.password_hash):
            return False, "Incorrect current password"

        # 验证新密码
        valid, error = validate_password(new_password)
        if not valid:
            return False, error

        # 更新密码（通过repository需要添加方法）
        # TODO: 实现密码更新
        return True, ""


# ==================== Streamlit集成工具 ====================

class StreamlitAuthManager:
    """Streamlit认证管理器"""

    def __init__(self):
        self.auth_service = AuthService()

    def init_session(self):
        """初始化Streamlit会话状态"""
        import streamlit as st

        if "auth_token" not in st.session_state:
            st.session_state.auth_token = None
        if "current_user" not in st.session_state:
            st.session_state.current_user = None

    def is_authenticated(self) -> bool:
        """检查用户是否已登录"""
        import streamlit as st

        if not st.session_state.get("auth_token"):
            return False

        # 验证令牌
        user = self.auth_service.get_current_user(st.session_state.auth_token)
        if not user:
            # 令牌无效，清除状态
            st.session_state.auth_token = None
            st.session_state.current_user = None
            return False

        st.session_state.current_user = user
        return True

    def login(self, email: str, password: str) -> Tuple[bool, str]:
        """登录并更新会话"""
        import streamlit as st

        token, error = self.auth_service.login(email, password)
        if token:
            st.session_state.auth_token = token
            user = self.auth_service.get_current_user(token)
            st.session_state.current_user = user
            return True, ""
        return False, error

    def register(self, email: str, password: str) -> Tuple[bool, str]:
        """注册"""
        user, error = self.auth_service.register(email, password)
        if user:
            return True, ""
        return False, error

    def logout(self):
        """登出"""
        import streamlit as st

        st.session_state.auth_token = None
        st.session_state.current_user = None

    def get_current_user_id(self) -> Optional[str]:
        """获取当前用户ID"""
        import streamlit as st

        user = st.session_state.get("current_user")
        return user.id if user else None

    def require_auth(self) -> bool:
        """
        要求用户登录，显示登录界面

        Returns:
            True if authenticated, False otherwise
        """
        import streamlit as st

        self.init_session()

        if self.is_authenticated():
            return True

        # 显示登录/注册选项卡
        tab_login, tab_register = st.tabs(["Login", "Register"])

        with tab_login:
            st.subheader("Login")
            email = st.text_input("Email", key="login_email")
            password = st.text_input("Password", type="password", key="login_password")

            if st.button("Login", key="btn_login"):
                if email and password:
                    success, error = self.login(email, password)
                    if success:
                        st.success("Login successful!")
                        st.rerun()
                    else:
                        st.error(error)
                else:
                    st.error("Please enter both email and password")

        with tab_register:
            st.subheader("Register")
            reg_email = st.text_input("Email", key="reg_email")
            reg_password = st.text_input("Password", type="password", key="reg_password")
            reg_password_confirm = st.text_input(
                "Confirm Password", type="password", key="reg_password_confirm"
            )

            st.info("Password must be at least 8 characters with letters and numbers")

            if st.button("Register", key="btn_register"):
                if reg_email and reg_password:
                    if reg_password != reg_password_confirm:
                        st.error("Passwords do not match")
                    else:
                        success, error = self.register(reg_email, reg_password)
                        if success:
                            st.success("Registration successful! Please login.")
                        else:
                            st.error(error)
                else:
                    st.error("Please fill in all fields")

        return False

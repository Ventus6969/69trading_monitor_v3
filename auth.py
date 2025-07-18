#!/usr/bin/env python3
"""
69交易機器人監控系統 - 簡單登入認證模組
提供基於session的簡單認證機制
=============================================================================
"""
import hashlib
import secrets
from datetime import datetime
from functools import wraps
from flask import session, request, redirect, url_for, flash, render_template_string

# 簡單的用戶憑證配置 (生產環境建議使用環境變量)
USERS = {
    "admin": "admin69"  # 唯一管理員帳號
}

def hash_password(password):
    """簡單的密碼哈希"""
    return hashlib.sha256(password.encode()).hexdigest()

def verify_password(username, password):
    """驗證用戶憑證"""
    if username in USERS:
        return USERS[username] == password
    return False

def login_required(f):
    """登入裝飾器"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'logged_in' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def setup_auth_routes(app):
    """設置認證相關路由"""
    
    @app.route('/login', methods=['GET', 'POST'])
    def login():
        """登入頁面"""
        if request.method == 'POST':
            username = request.form.get('username')
            password = request.form.get('password')
            
            if verify_password(username, password):
                session['logged_in'] = True
                session['username'] = username
                session['login_time'] = datetime.now().isoformat()
                
                # 生成安全的session token
                if 'csrf_token' not in session:
                    session['csrf_token'] = secrets.token_hex(16)
                
                flash('登入成功！', 'success')
                return redirect(url_for('dashboard'))
            else:
                flash('用戶名或密碼錯誤', 'error')
        
        return render_template_string(LOGIN_TEMPLATE)
    
    @app.route('/logout')
    def logout():
        """登出"""
        session.clear()
        flash('已成功登出', 'info')
        return redirect(url_for('login'))
    
    @app.route('/auth-status')
    def auth_status():
        """認證狀態API"""
        return {
            'logged_in': 'logged_in' in session,
            'username': session.get('username'),
            'login_time': session.get('login_time'),
            'session_id': request.cookies.get('session')
        }

# 登入頁面HTML模板 - 科技風格
LOGIN_TEMPLATE = '''
<!DOCTYPE html>
<html lang="zh-TW">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Trading Bot Monitor - Login</title>
    <link href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.4.0/css/all.min.css" rel="stylesheet">
    <style>
        :root {
            --bg-primary: #0a0e1a;
            --bg-secondary: #111827;
            --bg-tertiary: #1f2937;
            --accent-cyan: #00f5ff;
            --accent-blue: #3b82f6;
            --accent-green: #10b981;
            --accent-red: #ef4444;
            --text-primary: #f9fafb;
            --text-secondary: #9ca3af;
            --text-muted: #6b7280;
            --border-color: #374151;
            --glass-bg: rgba(31, 41, 55, 0.8);
            --shadow-glow: rgba(0, 245, 255, 0.3);
        }

        * {
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }

        body {
            font-family: 'SF Pro Display', -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: var(--bg-primary);
            color: var(--text-primary);
            min-height: 100vh;
            display: flex;
            align-items: center;
            justify-content: center;
            overflow: hidden;
        }

        /* 動態背景 */
        .bg-animation {
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: -1;
            background: radial-gradient(ellipse at center, rgba(0, 245, 255, 0.1) 0%, transparent 70%);
        }

        .bg-animation::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: url('data:image/svg+xml,<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 100 100"><circle cx="20" cy="20" r="2" fill="%2300f5ff" opacity="0.3"><animate attributeName="opacity" values="0.3;0.8;0.3" dur="2s" repeatCount="indefinite"/></circle><circle cx="80" cy="40" r="1" fill="%233b82f6" opacity="0.4"><animate attributeName="opacity" values="0.4;0.9;0.4" dur="3s" repeatCount="indefinite"/></circle><circle cx="60" cy="80" r="1.5" fill="%2310b981" opacity="0.2"><animate attributeName="opacity" values="0.2;0.7;0.2" dur="2.5s" repeatCount="indefinite"/></circle></svg>') repeat;
            animation: float 30s infinite linear;
        }

        @keyframes float {
            0% { transform: translateY(100vh) translateX(0); }
            100% { transform: translateY(-100vh) translateX(50px); }
        }

        /* 主要登入容器 */
        .login-container {
            background: var(--glass-bg);
            backdrop-filter: blur(20px);
            border: 1px solid var(--border-color);
            border-radius: 2rem;
            padding: 0;
            width: 100%;
            max-width: 420px;
            box-shadow: 0 25px 50px rgba(0, 0, 0, 0.5), 0 0 50px var(--shadow-glow);
            overflow: hidden;
            position: relative;
        }

        .login-container::before {
            content: '';
            position: absolute;
            top: 0;
            left: 0;
            right: 0;
            height: 3px;
            background: linear-gradient(90deg, var(--accent-cyan), var(--accent-blue), var(--accent-green));
            animation: shimmer 3s infinite;
        }

        @keyframes shimmer {
            0% { transform: translateX(-100%); }
            100% { transform: translateX(100%); }
        }

        .login-header {
            background: linear-gradient(135deg, var(--bg-secondary), var(--bg-tertiary));
            padding: 3rem 2rem 2rem;
            text-align: center;
            border-bottom: 1px solid var(--border-color);
        }

        .login-logo {
            display: inline-flex;
            width: 4rem;
            height: 4rem;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            border-radius: 1rem;
            align-items: center;
            justify-content: center;
            margin-bottom: 1rem;
            font-size: 2rem;
            color: var(--bg-primary);
            animation: pulse 3s infinite;
        }

        @keyframes pulse {
            0%, 100% { 
                transform: scale(1); 
                box-shadow: 0 0 0 0 var(--shadow-glow);
            }
            50% { 
                transform: scale(1.05); 
                box-shadow: 0 0 0 20px rgba(0, 245, 255, 0);
            }
        }

        .login-title {
            font-size: 1.8rem;
            font-weight: 700;
            margin-bottom: 0.5rem;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            -webkit-background-clip: text;
            -webkit-text-fill-color: transparent;
            background-clip: text;
        }

        .login-subtitle {
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 500;
        }

        .login-body {
            padding: 2rem;
        }

        .form-group {
            margin-bottom: 1.5rem;
        }

        .form-label {
            display: block;
            margin-bottom: 0.5rem;
            color: var(--text-secondary);
            font-size: 0.9rem;
            font-weight: 500;
            text-transform: uppercase;
            letter-spacing: 0.5px;
        }

        .input-group {
            position: relative;
        }

        .input-icon {
            position: absolute;
            left: 1rem;
            top: 50%;
            transform: translateY(-50%);
            color: var(--text-muted);
            z-index: 1;
        }

        .form-control {
            width: 100%;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1rem 1rem 1rem 3rem;
            color: var(--text-primary);
            font-size: 1rem;
            transition: all 0.3s ease;
        }

        .form-control:focus {
            outline: none;
            border-color: var(--accent-cyan);
            box-shadow: 0 0 0 3px rgba(0, 245, 255, 0.1);
            background: var(--bg-secondary);
        }

        .form-control::placeholder {
            color: var(--text-muted);
        }

        .btn-login {
            width: 100%;
            background: linear-gradient(135deg, var(--accent-cyan), var(--accent-blue));
            color: var(--bg-primary);
            padding: 1rem 2rem;
            border: none;
            border-radius: 1rem;
            font-size: 1rem;
            font-weight: 600;
            text-transform: uppercase;
            letter-spacing: 1px;
            cursor: pointer;
            transition: all 0.3s ease;
            position: relative;
            overflow: hidden;
        }

        .btn-login:hover {
            transform: translateY(-2px);
            box-shadow: 0 15px 35px var(--shadow-glow);
        }

        .btn-login:active {
            transform: translateY(0);
        }

        .btn-login::before {
            content: '';
            position: absolute;
            top: 0;
            left: -100%;
            width: 100%;
            height: 100%;
            background: linear-gradient(90deg, transparent, rgba(255, 255, 255, 0.2), transparent);
            transition: left 0.5s;
        }

        .btn-login:hover::before {
            left: 100%;
        }

        .system-info {
            background: linear-gradient(135deg, var(--bg-tertiary), var(--bg-secondary));
            border: 1px solid var(--border-color);
            border-radius: 1rem;
            padding: 1rem;
            margin-top: 1.5rem;
            text-align: center;
            font-size: 0.8rem;
            color: var(--text-secondary);
        }

        .default-accounts {
            margin-top: 2rem;
            text-align: center;
            color: var(--text-muted);
            font-size: 0.8rem;
        }

        .default-accounts .account {
            display: inline-block;
            background: var(--bg-tertiary);
            border: 1px solid var(--border-color);
            border-radius: 0.5rem;
            padding: 0.5rem 1rem;
            margin: 0.25rem;
            font-family: 'Courier New', monospace;
        }

        .alert {
            padding: 1rem;
            border-radius: 1rem;
            margin-bottom: 1rem;
            border: 1px solid;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }

        .alert-danger {
            background: rgba(239, 68, 68, 0.1);
            border-color: var(--accent-red);
            color: var(--accent-red);
        }

        .alert-success {
            background: rgba(16, 185, 129, 0.1);
            border-color: var(--accent-green);
            color: var(--accent-green);
        }

        .alert-info {
            background: rgba(59, 130, 246, 0.1);
            border-color: var(--accent-blue);
            color: var(--accent-blue);
        }

        .btn-close {
            margin-left: auto;
            background: none;
            border: none;
            color: inherit;
            cursor: pointer;
            opacity: 0.7;
        }

        .btn-close:hover {
            opacity: 1;
        }

        /* 響應式設計 */
        @media (max-width: 480px) {
            .login-container {
                margin: 1rem;
                max-width: none;
            }

            .login-header {
                padding: 2rem 1.5rem 1.5rem;
            }

            .login-body {
                padding: 1.5rem;
            }

            .login-title {
                font-size: 1.5rem;
            }
        }

        /* 載入動畫 */
        .loading {
            opacity: 0.7;
            pointer-events: none;
        }

        .loading .btn-login {
            background: var(--bg-tertiary);
        }
    </style>
</head>
<body>
    <div class="bg-animation"></div>

    <div class="login-container">
        <div class="login-header">
            <div class="login-logo">
                <i class="fas fa-robot"></i>
            </div>
            <h1 class="login-title">Trading Bot</h1>
            <p class="login-subtitle">Monitor System v3.2</p>
        </div>
        
        <div class="login-body">
            {% with messages = get_flashed_messages(with_categories=true) %}
                {% if messages %}
                    {% for category, message in messages %}
                        <div class="alert alert-{{ 'danger' if category == 'error' else category }}">
                            <i class="fas fa-{{ 'exclamation-triangle' if category == 'error' else 'info-circle' }}"></i>
                            {{ message }}
                            <button type="button" class="btn-close" onclick="this.parentElement.remove()">
                                <i class="fas fa-times"></i>
                            </button>
                        </div>
                    {% endfor %}
                {% endif %}
            {% endwith %}
            
            <form method="POST" id="loginForm">
                <div class="form-group">
                    <label for="username" class="form-label">Username</label>
                    <div class="input-group">
                        <i class="fas fa-user input-icon"></i>
                        <input type="text" 
                               class="form-control" 
                               id="username" 
                               name="username" 
                               placeholder="Enter your username"
                               required 
                               autocomplete="username">
                    </div>
                </div>
                
                <div class="form-group">
                    <label for="password" class="form-label">Password</label>
                    <div class="input-group">
                        <i class="fas fa-lock input-icon"></i>
                        <input type="password" 
                               class="form-control" 
                               id="password" 
                               name="password" 
                               placeholder="Enter your password"
                               required 
                               autocomplete="current-password">
                    </div>
                </div>
                
                <button type="submit" class="btn-login">
                    <i class="fas fa-sign-in-alt"></i>
                    Access System
                </button>
            </form>
            
            <div class="system-info">
                <i class="fas fa-shield-alt"></i>
                Secure Access • Real-time Monitoring • AI Analytics
            </div>
        </div>
    </div>
    
    <!-- 系統信息提示 -->
    <div class="default-accounts">
        <div style="margin-bottom: 0.5rem;">
            <i class="fas fa-shield-alt"></i> Secure Login Required
        </div>
        <div style="font-size: 0.75rem; color: var(--text-muted);">
            Please contact administrator for access credentials
        </div>
    </div>

    <script>
        // 表單提交動畫
        document.getElementById('loginForm').addEventListener('submit', function() {
            const button = this.querySelector('.btn-login');
            const originalText = button.innerHTML;
            
            button.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Authenticating...';
            button.classList.add('loading');
            
            // 如果登入失敗，重置按鈕 (會由頁面重載處理)
            setTimeout(() => {
                if (button.classList.contains('loading')) {
                    button.innerHTML = originalText;
                    button.classList.remove('loading');
                }
            }, 3000);
        });

        // 輸入框聚焦效果
        document.querySelectorAll('.form-control').forEach(input => {
            input.addEventListener('focus', function() {
                this.parentElement.style.transform = 'scale(1.02)';
            });
            
            input.addEventListener('blur', function() {
                this.parentElement.style.transform = 'scale(1)';
            });
        });
    </script>
</body>
</html>
'''

# Session配置
def configure_session(app):
    """配置Flask session"""
    import os
    from datetime import timedelta
    
    # Session配置
    app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', '69trading_monitor_secret_key_2025')
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=8)  # 8小時有效期
    app.config['SESSION_COOKIE_SECURE'] = False  # 開發環境設為False，生產環境設為True
    app.config['SESSION_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SAMESITE'] = 'Lax'

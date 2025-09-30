# SQL Server 連線教學（Windows）

## 安裝需求
1. 安裝 **Microsoft ODBC Driver 17 for SQL Server**（必要）
2. 安裝 SQL Server / SSMS（選用）

## 建立資料庫與使用者（範例）
```sql
CREATE DATABASE finnews;
GO
USE finnews;
GO
CREATE LOGIN finnewsuser WITH PASSWORD = 'YourStrong!Passw0rd';
CREATE USER finnewsuser FOR LOGIN finnewsuser;
EXEC sp_addrolemember N'db_datareader', N'finnewsuser';
EXEC sp_addrolemember N'db_datawriter', N'finnewsuser';
```

## 設定 .env
將 `.env.mssql.example` 複製為 `.env` 並修改：
```
DB_URL=mssql+pyodbc://finnewsuser:YourStrong!Passw0rd@localhost:1433/finnews?driver=ODBC+Driver+17+for+SQL+Server&TrustServerCertificate=yes
```
## 開啟服務 & TCP/IP

打開 SQL Server Configuration Manager → SQL Server Network Configuration
把 TCP/IP 設為 Enabled
TCP/IP → Properties → IP Addresses
    IPAll：
        TCP Dynamic Ports → 清空
        TCP Port → 填 1433（或你要的固定埠）

重啟 SQL Server 服務
(要給外部使用要開防火牆 Windows 防火牆或雲端安全群組：開放 TCP 1433)

## 安裝套件與測試
```bash
python -m venv .venv
.\.venv\Scripts\activate
pip install -r requirements.txt
python scripts/mssql_test_connection.py
```

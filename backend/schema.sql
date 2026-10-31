IF OBJECT_ID('dbo.Supplier') IS NULL
CREATE TABLE dbo.Supplier (id INT PRIMARY KEY, name NVARCHAR(160) NOT NULL, country NVARCHAR(80) NOT NULL, category NVARCHAR(60) NOT NULL, latitude FLOAT NOT NULL, longitude FLOAT NOT NULL, payload NVARCHAR(MAX) NOT NULL CHECK(ISJSON(payload)=1));
IF OBJECT_ID('dbo.Component') IS NULL
CREATE TABLE dbo.Component (id INT PRIMARY KEY, name NVARCHAR(160) NOT NULL, importance INT NOT NULL CHECK(importance BETWEEN 1 AND 10), payload NVARCHAR(MAX) NOT NULL CHECK(ISJSON(payload)=1));
IF OBJECT_ID('dbo.SupplyRelationship') IS NULL
CREATE TABLE dbo.SupplyRelationship (supplier_id INT REFERENCES dbo.Supplier(id), component_id INT REFERENCES dbo.Component(id), PRIMARY KEY(supplier_id,component_id));
IF OBJECT_ID('dbo.RiskEvent') IS NULL
CREATE TABLE dbo.RiskEvent (id NVARCHAR(100) PRIMARY KEY, fingerprint CHAR(64) UNIQUE NOT NULL, demo BIT NOT NULL DEFAULT 0, expires_at DATETIME2 NOT NULL, payload NVARCHAR(MAX) NOT NULL CHECK(ISJSON(payload)=1));

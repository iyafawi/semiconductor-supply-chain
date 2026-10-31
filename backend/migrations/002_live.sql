IF OBJECT_ID('dbo.SchemaMigration') IS NULL CREATE TABLE dbo.SchemaMigration(version INT PRIMARY KEY, applied_at DATETIME2 NOT NULL DEFAULT SYSUTCDATETIME());
IF OBJECT_ID('dbo.Article') IS NULL CREATE TABLE dbo.Article (
 id CHAR(64) PRIMARY KEY, source_id NVARCHAR(100) NOT NULL, source NVARCHAR(200) NOT NULL,
 title NVARCHAR(1000) NOT NULL, description NVARCHAR(MAX) NOT NULL, url NVARCHAR(2048) NOT NULL,
 published_at DATETIME2 NOT NULL, retrieved_at DATETIME2 NOT NULL, processing_status NVARCHAR(40) NOT NULL DEFAULT 'pending',
 processing_reason NVARCHAR(500) NULL, raw_metadata NVARCHAR(MAX) NOT NULL CHECK(ISJSON(raw_metadata)=1));
IF OBJECT_ID('dbo.LiveEvent') IS NULL CREATE TABLE dbo.LiveEvent (
 id CHAR(64) PRIMARY KEY, event_type NVARCHAR(50) NOT NULL, title NVARCHAR(1000) NOT NULL,
 severity FLOAT NOT NULL CHECK(severity BETWEEN 0 AND 1), confidence FLOAT NOT NULL CHECK(confidence BETWEEN 0 AND 1),
 credibility FLOAT NOT NULL CHECK(credibility BETWEEN 0 AND 1), region NVARCHAR(500) NOT NULL,
 event_risk FLOAT NOT NULL CHECK(event_risk BETWEEN 0 AND 1), first_seen DATETIME2 NOT NULL, last_seen DATETIME2 NOT NULL,
 published_at DATETIME2 NOT NULL, status NVARCHAR(50) NOT NULL, explanation NVARCHAR(MAX) NOT NULL,
 payload NVARCHAR(MAX) NOT NULL CHECK(ISJSON(payload)=1));
IF OBJECT_ID('dbo.EventArticle') IS NULL CREATE TABLE dbo.EventArticle (
 event_id CHAR(64) NOT NULL REFERENCES dbo.LiveEvent(id), article_id CHAR(64) NOT NULL REFERENCES dbo.Article(id), PRIMARY KEY(event_id,article_id));
IF OBJECT_ID('dbo.EventSupplier') IS NULL CREATE TABLE dbo.EventSupplier (
 event_id CHAR(64) NOT NULL REFERENCES dbo.LiveEvent(id), supplier_id INT NOT NULL REFERENCES dbo.Supplier(id),
 match_type NVARCHAR(20) NOT NULL CHECK(match_type IN ('direct','regional')),
 exposure_status NVARCHAR(50) NOT NULL CHECK(exposure_status IN ('confirmed_report','potential_exposure','low_confidence')),
 PRIMARY KEY(event_id,supplier_id));
IF OBJECT_ID('dbo.SupplierRisk') IS NULL CREATE TABLE dbo.SupplierRisk (
 supplier_id INT PRIMARY KEY REFERENCES dbo.Supplier(id), current_live_risk FLOAT NOT NULL CHECK(current_live_risk BETWEEN 0 AND 1),
 risk_level NVARCHAR(20) NOT NULL, active_event_id CHAR(64) NULL REFERENCES dbo.LiveEvent(id),
 exposure_status NVARCHAR(50) NOT NULL, updated_at DATETIME2 NOT NULL);
IF OBJECT_ID('dbo.SupplierRiskHistory') IS NULL CREATE TABLE dbo.SupplierRiskHistory (
 id BIGINT IDENTITY PRIMARY KEY, supplier_id INT NOT NULL REFERENCES dbo.Supplier(id), current_live_risk FLOAT NOT NULL,
 active_event_id CHAR(64) NULL, exposure_status NVARCHAR(50) NOT NULL, recorded_at DATETIME2 NOT NULL);
IF OBJECT_ID('dbo.RegionalRisk') IS NULL CREATE TABLE dbo.RegionalRisk (
 region NVARCHAR(100) PRIMARY KEY, current_live_risk FLOAT NOT NULL CHECK(current_live_risk BETWEEN 0 AND 1),
 active_event_id CHAR(64) NULL REFERENCES dbo.LiveEvent(id), exposed_suppliers INT NOT NULL, updated_at DATETIME2 NOT NULL);
IF OBJECT_ID('dbo.RegionalRiskHistory') IS NULL CREATE TABLE dbo.RegionalRiskHistory (
 id BIGINT IDENTITY PRIMARY KEY, region NVARCHAR(100) NOT NULL, current_live_risk FLOAT NOT NULL,
 active_event_id CHAR(64) NULL, recorded_at DATETIME2 NOT NULL);
IF OBJECT_ID('dbo.SourceState') IS NULL CREATE TABLE dbo.SourceState (
 source_id NVARCHAR(100) PRIMARY KEY, name NVARCHAR(200) NOT NULL, url NVARCHAR(2048) NOT NULL,
 etag NVARCHAR(1000) NULL, last_modified NVARCHAR(1000) NULL, last_attempt DATETIME2 NULL, last_success DATETIME2 NULL,
 status NVARCHAR(40) NOT NULL, last_error NVARCHAR(500) NULL, retrieved_count INT NOT NULL DEFAULT 0, new_count INT NOT NULL DEFAULT 0);
IF OBJECT_ID('dbo.IngestionRun') IS NULL CREATE TABLE dbo.IngestionRun (
 id BIGINT IDENTITY PRIMARY KEY, started_at DATETIME2 NOT NULL, finished_at DATETIME2 NOT NULL,
 sources_ok INT NOT NULL, sources_failed INT NOT NULL, articles_new INT NOT NULL, events_processed INT NOT NULL);
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE name='IX_Article_Pending' AND object_id=OBJECT_ID('dbo.Article')) CREATE INDEX IX_Article_Pending ON dbo.Article(processing_status,published_at);
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE name='IX_LiveEvent_Date' AND object_id=OBJECT_ID('dbo.LiveEvent')) CREATE INDEX IX_LiveEvent_Date ON dbo.LiveEvent(published_at);
IF NOT EXISTS(SELECT 1 FROM sys.indexes WHERE name='IX_RiskHistory_Supplier' AND object_id=OBJECT_ID('dbo.SupplierRiskHistory')) CREATE INDEX IX_RiskHistory_Supplier ON dbo.SupplierRiskHistory(supplier_id,recorded_at);
IF NOT EXISTS(SELECT 1 FROM dbo.SchemaMigration WHERE version=2) INSERT dbo.SchemaMigration(version) VALUES(2);

# 20-30 SQL Server DDL test cases covering the scenarios required in Phase 3.
# Each case: name, category, input DDL, and (optionally) notes on what it's probing.
# Expected/golden output lives in golden_outputs.json (generated once from a
# manually-reviewed run of the converter, then treated as the regression baseline).

TEST_CASES = [
    {
        "id": "TC01",
        "category": "Simple table",
        "name": "Basic single-column table",
        "input": """
CREATE TABLE dbo.Country (
    CountryCode CHAR(2) NOT NULL,
    CountryName VARCHAR(100) NOT NULL
);
"""
    },
    {
        "id": "TC02",
        "category": "Identity + PK",
        "name": "Worked example: Customer",
        "input": """
CREATE TABLE dbo.Customer (
    CustomerID INT IDENTITY(1,1) NOT NULL,
    CustomerName VARCHAR(100) NOT NULL,
    Email VARCHAR(255),
    DateOfBirth DATETIME,
    IsActive BIT DEFAULT 1,
    CreatedDate DATETIME2 DEFAULT GETDATE(),
    CONSTRAINT PK_Customer PRIMARY KEY (CustomerID)
);
"""
    },
    {
        "id": "TC03",
        "category": "Multiple data types",
        "name": "Product catalog with many numeric/string types",
        "input": """
CREATE TABLE dbo.Product (
    ProductID INT IDENTITY(1,1) NOT NULL,
    SKU CHAR(10) NOT NULL,
    ProductName NVARCHAR(200) NOT NULL,
    Description NVARCHAR(MAX),
    UnitPrice DECIMAL(10,2) NOT NULL,
    Weight FLOAT,
    IsDiscontinued BIT DEFAULT 0,
    ReleaseDate DATE,
    CONSTRAINT PK_Product PRIMARY KEY (ProductID)
);
"""
    },
    {
        "id": "TC04",
        "category": "Foreign key",
        "name": "Order referencing Customer",
        "input": """
CREATE TABLE dbo.[Order] (
    OrderID INT IDENTITY(1,1) NOT NULL,
    CustomerID INT NOT NULL,
    OrderDate DATETIME2 DEFAULT GETDATE(),
    CONSTRAINT PK_Order PRIMARY KEY (OrderID),
    CONSTRAINT FK_Order_Customer FOREIGN KEY (CustomerID) REFERENCES dbo.Customer(CustomerID)
);
"""
    },
    {
        "id": "TC05",
        "category": "Foreign key with cascade",
        "name": "OrderLine with ON DELETE CASCADE",
        "input": """
CREATE TABLE dbo.OrderLine (
    OrderLineID INT IDENTITY(1,1) NOT NULL,
    OrderID INT NOT NULL,
    ProductID INT NOT NULL,
    Quantity INT NOT NULL DEFAULT 1,
    CONSTRAINT PK_OrderLine PRIMARY KEY (OrderLineID),
    CONSTRAINT FK_OrderLine_Order FOREIGN KEY (OrderID) REFERENCES dbo.[Order](OrderID) ON DELETE CASCADE,
    CONSTRAINT FK_OrderLine_Product FOREIGN KEY (ProductID) REFERENCES dbo.Product(ProductID) ON UPDATE NO ACTION
);
"""
    },
    {
        "id": "TC06",
        "category": "Composite primary key",
        "name": "Many-to-many link table with composite PK",
        "input": """
CREATE TABLE dbo.StudentCourse (
    StudentID INT NOT NULL,
    CourseID INT NOT NULL,
    EnrolledDate DATE DEFAULT GETDATE(),
    CONSTRAINT PK_StudentCourse PRIMARY KEY (StudentID, CourseID)
);
"""
    },
    {
        "id": "TC07",
        "category": "Default values",
        "name": "Table exercising several default literal styles",
        "input": """
CREATE TABLE dbo.Settings (
    SettingID INT IDENTITY(1,1) NOT NULL,
    IsEnabled BIT DEFAULT ((1)),
    RetryCount INT DEFAULT ((0)),
    Environment VARCHAR(20) DEFAULT ('production'),
    LastRun DATETIME2 DEFAULT (GETDATE())
);
"""
    },
    {
        "id": "TC08",
        "category": "Nullable columns",
        "name": "Mix of NULL / NOT NULL / omitted",
        "input": """
CREATE TABLE dbo.Address (
    AddressID INT IDENTITY(1,1) NOT NULL,
    Line1 VARCHAR(200) NOT NULL,
    Line2 VARCHAR(200) NULL,
    City VARCHAR(100) NOT NULL,
    PostalCode VARCHAR(20)
);
"""
    },
    {
        "id": "TC09",
        "category": "Constraints",
        "name": "UNIQUE and CHECK constraints",
        "input": """
CREATE TABLE dbo.Employee (
    EmployeeID INT IDENTITY(1,1) NOT NULL,
    Email VARCHAR(255) NOT NULL,
    Salary DECIMAL(12,2) NOT NULL,
    CONSTRAINT PK_Employee PRIMARY KEY (EmployeeID),
    CONSTRAINT UQ_Employee_Email UNIQUE (Email),
    CONSTRAINT CK_Employee_Salary CHECK (Salary > 0)
);
"""
    },
    {
        "id": "TC10",
        "category": "Schema names",
        "name": "Non-default schema is preserved",
        "input": """
CREATE TABLE sales.Invoice (
    InvoiceID INT IDENTITY(1,1) NOT NULL,
    InvoiceNumber VARCHAR(30) NOT NULL,
    Total DECIMAL(12,2) NOT NULL
);
"""
    },
    {
        "id": "TC11",
        "category": "Reserved words",
        "name": "Table/column names collide with Snowflake reserved words",
        "input": """
CREATE TABLE dbo.[Order] (
    [Order] INT IDENTITY(1,1) NOT NULL,
    [Group] VARCHAR(50),
    [Table] VARCHAR(50),
    [Select] VARCHAR(50)
);
"""
    },
    {
        "id": "TC12",
        "category": "Large VARCHAR/NVARCHAR",
        "name": "MAX-length string columns",
        "input": """
CREATE TABLE dbo.Document (
    DocumentID INT IDENTITY(1,1) NOT NULL,
    Title NVARCHAR(400),
    Body NVARCHAR(MAX),
    RawText VARCHAR(MAX)
);
"""
    },
    {
        "id": "TC13",
        "category": "Decimal precision/scale",
        "name": "Several DECIMAL/NUMERIC precision-scale combos",
        "input": """
CREATE TABLE dbo.FinancialLedger (
    LedgerID INT IDENTITY(1,1) NOT NULL,
    Amount DECIMAL(18,4) NOT NULL,
    TaxRate NUMERIC(5,4) NOT NULL,
    Balance DECIMAL(38,0) NOT NULL
);
"""
    },
    {
        "id": "TC14",
        "category": "Date/time types",
        "name": "All SQL Server date/time variants in one table",
        "input": """
CREATE TABLE dbo.EventLog (
    EventID INT IDENTITY(1,1) NOT NULL,
    EventDate DATE,
    EventTime TIME,
    EventDateTime DATETIME,
    EventDateTime2 DATETIME2,
    EventSmallDateTime SMALLDATETIME,
    EventOffset DATETIMEOFFSET
);
"""
    },
    {
        "id": "TC15",
        "category": "Unsupported feature",
        "name": "UNIQUEIDENTIFIER + NEWID()",
        "input": """
CREATE TABLE dbo.SessionToken (
    TokenID UNIQUEIDENTIFIER NOT NULL DEFAULT NEWID(),
    UserID INT NOT NULL,
    IssuedAt DATETIME2 DEFAULT GETUTCDATE()
);
"""
    },
    {
        "id": "TC16",
        "category": "Unsupported feature",
        "name": "ROWVERSION / TIMESTAMP column",
        "input": """
CREATE TABLE dbo.InventoryItem (
    ItemID INT IDENTITY(1,1) NOT NULL,
    Quantity INT NOT NULL,
    RowVersionCol ROWVERSION
);
"""
    },
    {
        "id": "TC17",
        "category": "Unsupported feature",
        "name": "Computed column",
        "input": """
CREATE TABLE dbo.OrderTotal (
    OrderTotalID INT IDENTITY(1,1) NOT NULL,
    Quantity INT NOT NULL,
    UnitPrice DECIMAL(10,2) NOT NULL,
    LineTotal AS (Quantity * UnitPrice)
);
"""
    },
    {
        "id": "TC18",
        "category": "Unsupported feature",
        "name": "XML column type",
        "input": """
CREATE TABLE dbo.Configuration (
    ConfigID INT IDENTITY(1,1) NOT NULL,
    Payload XML
);
"""
    },
    {
        "id": "TC19",
        "category": "Table options",
        "name": "Filegroup / WITH options that must be stripped",
        "input": """
CREATE TABLE dbo.BigTable (
    RowID INT IDENTITY(1,1) NOT NULL,
    Payload VARBINARY(MAX)
) ON [PRIMARY] TEXTIMAGE_ON [PRIMARY];
"""
    },
    {
        "id": "TC20",
        "category": "Clustered index hint",
        "name": "PRIMARY KEY CLUSTERED",
        "input": """
CREATE TABLE dbo.Region (
    RegionID INT IDENTITY(1,1) NOT NULL,
    RegionName VARCHAR(100) NOT NULL,
    CONSTRAINT PK_Region PRIMARY KEY CLUSTERED (RegionID)
);
"""
    },
    {
        "id": "TC21",
        "category": "Inline index",
        "name": "Inline NONCLUSTERED INDEX definition",
        "input": """
CREATE TABLE dbo.Ticket (
    TicketID INT IDENTITY(1,1) NOT NULL,
    Subject VARCHAR(200) NOT NULL,
    INDEX IX_Ticket_Subject NONCLUSTERED (Subject)
);
"""
    },
    {
        "id": "TC22",
        "category": "ISNULL function",
        "name": "CHECK constraint using ISNULL",
        "input": """
CREATE TABLE dbo.Coupon (
    CouponID INT IDENTITY(1,1) NOT NULL,
    DiscountPct DECIMAL(5,2),
    CONSTRAINT CK_Coupon_Discount CHECK (ISNULL(DiscountPct, 0) >= 0)
);
"""
    },
    {
        "id": "TC23",
        "category": "Money types",
        "name": "MONEY and SMALLMONEY columns",
        "input": """
CREATE TABLE dbo.Payroll (
    PayrollID INT IDENTITY(1,1) NOT NULL,
    GrossPay MONEY NOT NULL,
    Bonus SMALLMONEY
);
"""
    },
    {
        "id": "TC24",
        "category": "Binary types",
        "name": "BINARY / VARBINARY / IMAGE",
        "input": """
CREATE TABLE dbo.Attachment (
    AttachmentID INT IDENTITY(1,1) NOT NULL,
    Checksum BINARY(16),
    FileBytes VARBINARY(MAX),
    LegacyThumbnail IMAGE
);
"""
    },
    {
        "id": "TC25",
        "category": "Tiny/unsigned",
        "name": "TINYINT usage",
        "input": """
CREATE TABLE dbo.Rating (
    RatingID INT IDENTITY(1,1) NOT NULL,
    Stars TINYINT NOT NULL
);
"""
    },
    {
        "id": "TC26",
        "category": "Multiple tables in one batch",
        "name": "Two CREATE TABLE statements separated by GO",
        "input": """
CREATE TABLE dbo.Department (
    DepartmentID INT IDENTITY(1,1) NOT NULL,
    DepartmentName VARCHAR(100) NOT NULL,
    CONSTRAINT PK_Department PRIMARY KEY (DepartmentID)
);
GO
CREATE TABLE dbo.Team (
    TeamID INT IDENTITY(1,1) NOT NULL,
    DepartmentID INT NOT NULL,
    TeamName VARCHAR(100) NOT NULL,
    CONSTRAINT PK_Team PRIMARY KEY (TeamID),
    CONSTRAINT FK_Team_Department FOREIGN KEY (DepartmentID) REFERENCES dbo.Department(DepartmentID)
);
"""
    },
    {
        "id": "TC27",
        "category": "Data masking / collation",
        "name": "MASKED WITH and COLLATE column attributes",
        "input": """
CREATE TABLE dbo.Patient (
    PatientID INT IDENTITY(1,1) NOT NULL,
    SSN CHAR(11) MASKED WITH (FUNCTION = 'partial(0,"XXX-XX-",4)') NULL,
    LastName VARCHAR(100) COLLATE Latin1_General_CI_AS NOT NULL
);
"""
    },
    {
        "id": "TC28",
        "category": "Unknown/unmapped type",
        "name": "GEOGRAPHY / HIERARCHYID spatial & hierarchy types",
        "input": """
CREATE TABLE dbo.StoreLocation (
    StoreLocationID INT IDENTITY(1,1) NOT NULL,
    GeoPoint GEOGRAPHY,
    OrgPath HIERARCHYID
);
"""
    },
    {
        "id": "TC29",
        "category": "sql_variant/rowguidcol",
        "name": "SQL_VARIANT and ROWGUIDCOL attribute",
        "input": """
CREATE TABLE dbo.AuditEntry (
    AuditEntryID UNIQUEIDENTIFIER NOT NULL ROWGUIDCOL DEFAULT NEWID(),
    OldValue SQL_VARIANT,
    NewValue SQL_VARIANT
);
"""
    },
    {
        "id": "TC30",
        "category": "String default + BIT combos",
        "name": "Assorted defaults across a wider table (stress test)",
        "input": """
CREATE TABLE dbo.Subscription (
    SubscriptionID INT IDENTITY(1,1) NOT NULL,
    PlanName VARCHAR(50) NOT NULL DEFAULT 'free',
    AutoRenew BIT NOT NULL DEFAULT 0,
    TrialUsed BIT DEFAULT 1,
    MaxSeats SMALLINT DEFAULT 5,
    StartedAt DATETIME2 NOT NULL DEFAULT GETDATE(),
    ExpiresAt DATETIME2 NULL,
    CONSTRAINT PK_Subscription PRIMARY KEY (SubscriptionID)
);
"""
    },
]

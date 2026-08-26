CREATE TABLE employee (
  employee_id INT AUTO_INCREMENT,
  first_name VARCHAR(50) NOT NULL,
  last_name VARCHAR(50),
  email VARCHAR(150) UNIQUE,
  salary DECIMAL(12,2),
  hire_date DATE,
  is_active BOOLEAN DEFAULT TRUE,
  PRIMARY KEY (employee_id)
);

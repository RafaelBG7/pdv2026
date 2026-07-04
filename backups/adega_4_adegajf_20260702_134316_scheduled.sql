-- Backup Adega JF
-- Banco: adega_4_adegajf
-- Gerado em: 2026-07-02 13:43:16 UTC
SET FOREIGN_KEY_CHECKS=0;

-- Tabela: cash_registers
DROP TABLE IF EXISTS `cash_registers`;
CREATE TABLE `cash_registers` (
  `id` int NOT NULL AUTO_INCREMENT,
  `opened_at` datetime DEFAULT NULL,
  `closed_at` datetime DEFAULT NULL,
  `opening_amount` float DEFAULT NULL,
  `closing_amount` float DEFAULT NULL,
  `status` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `company_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `company_id` (`company_id`),
  CONSTRAINT `cash_registers_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `cash_registers_ibfk_2` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela: categories
DROP TABLE IF EXISTS `categories`;
CREATE TABLE `categories` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(120) COLLATE utf8mb4_unicode_ci NOT NULL,
  `company_id` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `company_id` (`company_id`),
  CONSTRAINT `categories_ibfk_1` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=4 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO `categories` (`id`, `name`, `company_id`, `created_at`) VALUES (2, 'Cerveja', 4, '2026-07-02 02:12:38');
INSERT INTO `categories` (`id`, `name`, `company_id`, `created_at`) VALUES (3, 'Refrigerante', 4, '2026-07-02 02:12:44');

-- Tabela: companies
DROP TABLE IF EXISTS `companies`;
CREATE TABLE `companies` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(160) COLLATE utf8mb4_unicode_ci NOT NULL,
  `database_path` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `subscription_plan` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `billing_cycle` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `subscription_started_at` date DEFAULT NULL,
  `subscription_renews_at` date DEFAULT NULL,
  `activation_key` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `activation_key_updated_at` datetime DEFAULT NULL,
  `card_fee_enabled` tinyint(1) DEFAULT NULL,
  `pix_fee_enabled` tinyint(1) DEFAULT NULL,
  `debit_fee_enabled` tinyint(1) DEFAULT NULL,
  `credit_fee_enabled` tinyint(1) DEFAULT NULL,
  `pix_fee_percent` float DEFAULT NULL,
  `debit_fee_percent` float DEFAULT NULL,
  `credit_fee_percent` float DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  `backup_frequency` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT 'manual',
  `backup_last_at` datetime DEFAULT NULL,
  `backup_last_path` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT '',
  `backup_last_status` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT '',
  PRIMARY KEY (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=5 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO `companies` (`id`, `name`, `database_path`, `active`, `subscription_plan`, `billing_cycle`, `subscription_started_at`, `subscription_renews_at`, `activation_key`, `activation_key_updated_at`, `card_fee_enabled`, `pix_fee_enabled`, `debit_fee_enabled`, `credit_fee_enabled`, `pix_fee_percent`, `debit_fee_percent`, `credit_fee_percent`, `created_at`, `backup_frequency`, `backup_last_at`, `backup_last_path`, `backup_last_status`) VALUES (4, 'AdegaJF', 'adega_4_adegajf', 1, 'Essencial', 'monthly', '2026-07-01', '2026-07-31', 'XX0D-Q93T-P3DN-PKFH', '2026-07-02 02:07:02', 0, 0, 0, 0, 0.0, 0.0, 0.0, '2026-07-02 02:07:02', 'daily', NULL, '/Users/rafaelborges/pdv-adega-jf/backups/adega_4_adegajf_20260702_134200_manual_test.sql', 'success');

-- Tabela: payables
DROP TABLE IF EXISTS `payables`;
CREATE TABLE `payables` (
  `id` int NOT NULL AUTO_INCREMENT,
  `company_id` int DEFAULT NULL,
  `description` varchar(180) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(80) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `amount` float DEFAULT NULL,
  `due_date` date NOT NULL,
  `paid` tinyint(1) DEFAULT NULL,
  `paid_at` datetime DEFAULT NULL,
  `notes` text COLLATE utf8mb4_unicode_ci,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `company_id` (`company_id`),
  CONSTRAINT `payables_ibfk_1` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela: payments
DROP TABLE IF EXISTS `payments`;
CREATE TABLE `payments` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sale_id` int DEFAULT NULL,
  `method` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `amount` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `sale_id` (`sale_id`),
  CONSTRAINT `payments_ibfk_1` FOREIGN KEY (`sale_id`) REFERENCES `sales` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela: products
DROP TABLE IF EXISTS `products`;
CREATE TABLE `products` (
  `id` int NOT NULL AUTO_INCREMENT,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `barcode` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `category_id` int DEFAULT NULL,
  `company_id` int DEFAULT NULL,
  `cost_price` float DEFAULT NULL,
  `sale_price` float DEFAULT NULL,
  `stock_quantity` int DEFAULT NULL,
  `min_stock_quantity` int DEFAULT NULL,
  `active` tinyint(1) DEFAULT NULL,
  `is_kit` tinyint(1) DEFAULT NULL,
  `kit_component_product_id` int DEFAULT NULL,
  `kit_component_quantity` int DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `category_id` (`category_id`),
  KEY `company_id` (`company_id`),
  KEY `kit_component_product_id` (`kit_component_product_id`),
  CONSTRAINT `products_ibfk_1` FOREIGN KEY (`category_id`) REFERENCES `categories` (`id`),
  CONSTRAINT `products_ibfk_2` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`),
  CONSTRAINT `products_ibfk_3` FOREIGN KEY (`kit_component_product_id`) REFERENCES `products` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela: sale_items
DROP TABLE IF EXISTS `sale_items`;
CREATE TABLE `sale_items` (
  `id` int NOT NULL AUTO_INCREMENT,
  `sale_id` int DEFAULT NULL,
  `product_id` int DEFAULT NULL,
  `quantity` int DEFAULT NULL,
  `unit_price` float DEFAULT NULL,
  `unit_cost_price` float DEFAULT NULL,
  `total_price` float DEFAULT NULL,
  `profit_amount` float DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `sale_id` (`sale_id`),
  KEY `product_id` (`product_id`),
  CONSTRAINT `sale_items_ibfk_1` FOREIGN KEY (`sale_id`) REFERENCES `sales` (`id`),
  CONSTRAINT `sale_items_ibfk_2` FOREIGN KEY (`product_id`) REFERENCES `products` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela: sales
DROP TABLE IF EXISTS `sales`;
CREATE TABLE `sales` (
  `id` int NOT NULL AUTO_INCREMENT,
  `created_at` datetime DEFAULT NULL,
  `total_amount` float DEFAULT NULL,
  `discount_amount` float DEFAULT NULL,
  `final_amount` float DEFAULT NULL,
  `payment_status` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_id` int DEFAULT NULL,
  `company_id` int DEFAULT NULL,
  `cash_register_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  KEY `user_id` (`user_id`),
  KEY `company_id` (`company_id`),
  KEY `cash_register_id` (`cash_register_id`),
  CONSTRAINT `sales_ibfk_1` FOREIGN KEY (`user_id`) REFERENCES `users` (`id`),
  CONSTRAINT `sales_ibfk_2` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`),
  CONSTRAINT `sales_ibfk_3` FOREIGN KEY (`cash_register_id`) REFERENCES `cash_registers` (`id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- Tabela: users
DROP TABLE IF EXISTS `users`;
CREATE TABLE `users` (
  `id` int NOT NULL AUTO_INCREMENT,
  `username` varchar(80) COLLATE utf8mb4_unicode_ci NOT NULL,
  `first_name` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `last_name` varchar(120) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `phone` varchar(40) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `password_hash` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `role` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `company_id` int DEFAULT NULL,
  `is_active` tinyint(1) DEFAULT NULL,
  `can_view_products` tinyint(1) DEFAULT NULL,
  `can_manage_products` tinyint(1) DEFAULT NULL,
  `can_manage_categories` tinyint(1) DEFAULT NULL,
  `can_manage_sales` tinyint(1) DEFAULT NULL,
  `can_manage_cash_register` tinyint(1) DEFAULT NULL,
  `can_view_reports` tinyint(1) DEFAULT NULL,
  `can_manage_payables` tinyint(1) DEFAULT NULL,
  `can_manage_settings` tinyint(1) DEFAULT NULL,
  `created_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `username` (`username`),
  KEY `company_id` (`company_id`),
  CONSTRAINT `users_ibfk_1` FOREIGN KEY (`company_id`) REFERENCES `companies` (`id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
INSERT INTO `users` (`id`, `username`, `first_name`, `last_name`, `email`, `phone`, `password_hash`, `role`, `company_id`, `is_active`, `can_view_products`, `can_manage_products`, `can_manage_categories`, `can_manage_sales`, `can_manage_cash_register`, `can_view_reports`, `can_manage_payables`, `can_manage_settings`, `created_at`) VALUES (5, 'AdegaJF', '', '', 'adegajf@saas.com', '', 'pbkdf2:sha256:1000000$swAwmHPIDq6yhrGG$8070365a5d4f9fb219f4977ea348f20b52048982cd723f0a12159ba69f9e329a', 'admin', 4, 1, 1, 1, 1, 1, 1, 1, 1, 1, '2026-07-02 02:07:02');

SET FOREIGN_KEY_CHECKS=1;

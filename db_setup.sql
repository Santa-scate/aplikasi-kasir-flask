-- Skrip Final untuk Setup Database di PythonAnywhere

-- Tabel untuk kategori produk
CREATE TABLE IF NOT EXISTS `category` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `nama` VARCHAR(100) NOT NULL UNIQUE
);

-- Tabel untuk user (admin/kasir)
CREATE TABLE IF NOT EXISTS `user` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `username` VARCHAR(80) UNIQUE NOT NULL,
  `password` VARCHAR(255) NOT NULL,
  `role` VARCHAR(20) NOT NULL DEFAULT 'kasir'
);

-- Tabel untuk produk
CREATE TABLE IF NOT EXISTS `product` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `kode_produk` VARCHAR(50) UNIQUE NOT NULL,
  `nama` VARCHAR(100) NOT NULL,
  `harga` INT NOT NULL,
  `stok` INT NOT NULL,
  `stok_minimum` INT NOT NULL DEFAULT 5,
  `category_id` INT NOT NULL,
  FOREIGN KEY (`category_id`) REFERENCES `category`(`id`)
);

-- Tabel utama untuk setiap transaksi
CREATE TABLE IF NOT EXISTS `transaction` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `tanggal` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `subtotal` INT NOT NULL,
  `diskon` INT NOT NULL DEFAULT 0,
  `grand_total` INT NOT NULL,
  `nama_kasir` VARCHAR(100) NOT NULL
);

-- Tabel detail item dalam setiap transaksi
CREATE TABLE IF NOT EXISTS `transaction_detail` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `transaction_id` INT NOT NULL,
  `product_id` INT NOT NULL,
  `jumlah` INT NOT NULL,
  `subtotal` INT NOT NULL,
  FOREIGN KEY (`transaction_id`) REFERENCES `transaction`(`id`) ON DELETE CASCADE,
  FOREIGN KEY (`product_id`) REFERENCES `product`(`id`)
);

-- Tabel untuk mencatat semua pergerakan stok
CREATE TABLE IF NOT EXISTS `stock_history` (
  `id` INT AUTO_INCREMENT PRIMARY KEY,
  `product_id` INT NOT NULL,
  `jumlah_perubahan` INT NOT NULL,
  `stok_sebelum` INT NOT NULL,
  `stok_sesudah` INT NOT NULL,
  `tipe_kegiatan` VARCHAR(50) NOT NULL,
  `keterangan` TEXT,
  `tanggal_perubahan` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
  `user_id` INT,
  FOREIGN KEY (`product_id`) REFERENCES `product`(`id`),
  FOREIGN KEY (`user_id`) REFERENCES `user`(`id`)
);

-- === DATA AWAL ===

-- Menambahkan satu user admin default dengan role 'admin'
-- Passwordnya adalah 'admin123'
INSERT INTO `user` (username, password, role)
SELECT 'admin', '$2b$12$4iwpM9iorRjN2l3aMH0Qeuby3IX2muIeWNiA3zM1NEV2M/2b/en72', 'admin'
WHERE NOT EXISTS (SELECT 1 FROM `user` WHERE username = 'admin');

-- Menambahkan satu kategori default
INSERT INTO `category` (nama)
SELECT 'Lain-lain'
WHERE NOT EXISTS (SELECT 1 FROM `category` WHERE nama = 'Lain-lain');

-- Menambahkan beberapa produk contoh
INSERT INTO `product` (kode_produk, nama, harga, stok, stok_minimum, category_id)
SELECT 'P001', 'Air Mineral 600ml', 3500, 100, 10, (SELECT id FROM category WHERE nama = 'Lain-lain') WHERE NOT EXISTS (SELECT 1 FROM `product` WHERE kode_produk = 'P001');
INSERT INTO `product` (kode_produk, nama, harga, stok, stok_minimum, category_id)
SELECT 'P002', 'Roti Coklat', 5000, 50, 5, (SELECT id FROM category WHERE nama = 'Lain-lain') WHERE NOT EXISTS (SELECT 1 FROM `product` WHERE kode_produk = 'P002');
INSERT INTO `product` (kode_produk, nama, harga, stok, stok_minimum, category_id)
SELECT 'P003', 'Snack Kentang', 8000, 75, 15, (SELECT id FROM category WHERE nama = 'Lain-lain') WHERE NOT EXISTS (SELECT 1 FROM `product` WHERE kode_produk = 'P003');



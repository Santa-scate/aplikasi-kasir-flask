// =================== LOGIKA KERANJANG (CART) ===================
let cart = [];

function formatRupiah(angka) {
    return new Intl.NumberFormat('id-ID', {
        style: 'currency',
        currency: 'IDR',
        minimumFractionDigits: 0
    }).format(angka);
}

function addToCart(productId, productName, productPrice, productStock) {
    productId = parseInt(productId);
    productPrice = parseInt(productPrice);
    productStock = parseInt(productStock);

    const existingItem = cart.find(item => item.id === productId);

    if (existingItem) {
        if (existingItem.quantity < productStock) {
            existingItem.quantity++;
        } else {
            alert(`Stok produk ${productName} tidak mencukupi!`);
        }
    } else {
        if (productStock > 0) {
            cart.push({ id: productId, name: productName, price: productPrice, quantity: 1, stock: productStock });
        } else {
             alert(`Stok produk ${productName} habis!`);
        }
    }
    renderCart();
}

function updateQuantity(productId, newQuantity) {
    const item = cart.find(item => item.id === productId);
    newQuantity = parseInt(newQuantity);

    if (item) {
        if (newQuantity > 0 && newQuantity <= item.stock) {
            item.quantity = newQuantity;
        } else if (newQuantity > item.stock) {
            item.quantity = item.stock;
            alert(`Stok maksimum untuk ${item.name} adalah ${item.stock}`);
        } else {
            removeFromCart(productId);
        }
    }
    renderCart();
}

function removeFromCart(productId) {
    cart = cart.filter(item => item.id !== productId);
    renderCart();
}

function renderCart() {
    const cartItems = document.getElementById('cart-items');
    const cartSubtotalEl = document.getElementById('cart-subtotal');
    const cartDiskonEl = document.getElementById('cart-diskon');
    const cartGrandTotalEl = document.getElementById('cart-grand-total');
    const diskonInput = document.getElementById('diskon-input');
    const btnBayar = document.getElementById('btn-bayar');
    const form = document.getElementById('transaction-form');
    
    if (!cartItems || !cartSubtotalEl || !cartDiskonEl || !cartGrandTotalEl || !diskonInput || !btnBayar || !form) {
        console.error("Satu atau lebih elemen keranjang tidak ditemukan di DOM.");
        return;
    }

    cartItems.innerHTML = '';
    let subtotal = 0;

    if (cart.length === 0) {
        cartItems.innerHTML = '<tr><td colspan="4" class="text-center text-muted">Keranjang kosong</td></tr>';
        btnBayar.disabled = true;
    } else {
        cart.forEach(item => {
            const itemTotal = item.price * item.quantity;
            subtotal += itemTotal;
            const row = document.createElement('tr');
            row.innerHTML = `
                <td>${item.name}</td>
                <td><input type="number" class="form-control form-control-sm" value="${item.quantity}" min="1" max="${item.stock}" onchange="updateQuantity(${item.id}, this.value)"></td>
                <td>${formatRupiah(itemTotal)}</td>
                <td><button class="btn btn-danger btn-sm" onclick="removeFromCart(${item.id})"><i class="bi bi-trash"></i></button></td>
            `;
            cartItems.appendChild(row);
        });
        btnBayar.disabled = false;
    }

    let diskon = parseInt(diskonInput.value) || 0;
    if (diskon > subtotal) {
        diskon = subtotal;
        diskonInput.value = diskon;
    }
    const grandTotal = subtotal - diskon;

    cartSubtotalEl.textContent = formatRupiah(subtotal);
    cartDiskonEl.textContent = `- ${formatRupiah(diskon)}`;
    cartGrandTotalEl.textContent = formatRupiah(grandTotal);
    
    form.querySelector('input[name="cart"]').value = JSON.stringify(cart.map(item => ({id: item.id, quantity: item.quantity, price: item.price})));
    form.querySelector('input[name="subtotal"]').value = subtotal;
    form.querySelector('input[name="diskon"]').value = diskon;
    form.querySelector('input[name="grand_total"]').value = grandTotal;
}

// =================== INISIALISASI SEMUA EVENT LISTENER ===================
document.addEventListener('DOMContentLoaded', function() {
    // ---- Barcode Scanner ----
    const barcodeForm = document.getElementById('barcode-form');
    const barcodeInput = document.getElementById('barcode-input');
    if (barcodeForm) {
        barcodeForm.addEventListener('submit', function(event) {
            event.preventDefault();
            const kodeProduk = barcodeInput.value.trim();
            if (kodeProduk === '') return;

            fetch(`/api/produk_by_kode/${kodeProduk}`)
                .then(response => {
                    if (!response.ok) throw new Error('Produk tidak ditemukan');
                    return response.json();
                })
                .then(product => {
                    addToCart(product.id, product.nama, product.harga, product.stok);
                })
                .catch(error => {
                    alert(`Error: ${error.message} dengan kode "${kodeProduk}"`);
                })
                .finally(() => {
                    barcodeInput.value = '';
                    barcodeInput.focus();
                });
        });
    }

    // ---- Tombol Tambah ke Keranjang (Event Delegation) ----
    const productList = document.getElementById('product-list');
    if (productList) {
        productList.addEventListener('click', function(event) {
            const button = event.target.closest('.add-to-cart-btn');
            if (button) {
                const id = button.dataset.id;
                const nama = button.dataset.nama;
                const harga = button.dataset.harga;
                const stok = button.dataset.stok;
                addToCart(id, nama, harga, stok);
            }
        });
    }

    // ---- Diskon ----
    const diskonInput = document.getElementById('diskon-input');
    if (diskonInput) {
        diskonInput.addEventListener('input', renderCart);
    }
    
    // Render keranjang pertama kali saat halaman dimuat
    renderCart();
});


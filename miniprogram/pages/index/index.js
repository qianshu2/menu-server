const API = getApp().globalData.apiBase;

Page({
  data: {
    apiBase: API,
    menu: [],
    loading: true,
    cart: {},
    cartList: [],
    cartCount: 0,
    totalPrice: 0
  },

  onLoad() {
    this.loadMenu();
  },

  onShow() {
    this.renderCart();
  },

  loadMenu() {
    wx.request({
      url: API + "/menu",
      success: (res) => {
        this.setData({ menu: res.data.data, loading: false });
      },
      fail: () => {
        wx.showToast({ title: "连接后端失败", icon: "error" });
        this.setData({ loading: false });
      }
    });
  },

  addToCart(e) {
    const name = e.currentTarget.dataset.name;
    const cart = this.data.cart;
    cart[name] = (cart[name] || 0) + 1;
    this.setData({ cart });
    this.renderCart();
    wx.showToast({ title: "已加入：" + name, icon: "none", duration: 1000 });
  },

  renderCart() {
    const cart = this.data.cart;
    const menu = this.data.menu;
    let cartList = [];
    let totalPrice = 0;
    let cartCount = 0;

    for (let name in cart) {
      const qty = cart[name];
      if (qty <= 0) continue;
      const dish = menu.find(d => d.name === name);
      if (!dish) continue;
      const subtotal = dish.price * qty;
      totalPrice += subtotal;
      cartCount += qty;
      cartList.push({ dish_name: name, quantity: qty, subtotal: subtotal });
    }

    this.setData({ cartList, cartCount, totalPrice });
  },

  submitOrder() {
    if (this.data.cartCount === 0) {
      wx.showToast({ title: "请先点菜！", icon: "none" });
      return;
    }

    const cart = this.data.cart;
    const orders = [];
    for (let name in cart) {
      if (cart[name] > 0) {
        orders.push({ dish_name: name, quantity: cart[name] });
      }
    }

    let done = 0;
    const total = orders.length;
    let errors = [];

    orders.forEach(o => {
      wx.request({
        url: API + "/order",
        method: "POST",
        data: o,
        success: () => {
          done++;
          if (done === total) this.finishOrder(errors);
        },
        fail: () => {
          done++;
          errors.push(o.dish_name);
          if (done === total) this.finishOrder(errors);
        }
      });
    });
  },

  finishOrder(errors) {
    if (errors.length > 0) {
      wx.showToast({ title: errors.join(",") + " 下单失败", icon: "error" });
    } else {
      wx.showToast({ title: "下单成功！", icon: "success" });
      this.setData({ cart: {}, cartList: [], cartCount: 0, totalPrice: 0 });
    }
  }
});

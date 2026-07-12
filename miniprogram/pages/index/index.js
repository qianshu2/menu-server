const API = getApp().globalData.apiBase;

const CAT_ICONS = {
  '烧菜': '../../images/cats/shaocai.png',
  '凉菜': '../../images/cats/liangcai.png',
  '汤羹': '../../images/cats/tanggeng.png',
  '主食': '../../images/cats/zhushi.png',
  '小吃': '../../images/cats/xiaochi.png',
  '饮品': '../../images/cats/yinpin.png'
};
const DEFAULT_ICON = '../../images/cats/default.png';

Page({
  data: {
    apiBase: API,
    menu: [],
    categories: [],
    grouped: {},
    loading: true,
    cart: {},
    cartList: [],
    cartCount: 0,
    note: "",
    activeCat: "",
    catList: []
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
        const menu = res.data.data;
        const categories = [];
        const grouped = {};
        menu.forEach(dish => {
          if (!grouped[dish.category]) {
            grouped[dish.category] = [];
            categories.push(dish.category);
          }
          grouped[dish.category].push(dish);
        });
        const catList = categories.map(c => ({
          name: c,
          icon: CAT_ICONS[c] || DEFAULT_ICON
        }));
        this.setData({ menu, categories, grouped, catList, activeCat: categories[0] || "", loading: false });
      },
      fail: () => {
        wx.showToast({ title: "加载失败", icon: "error" });
        this.setData({ loading: false });
      }
    });
  },

  // ===== 左侧分类切换 =====

  switchCat(e) {
    const cat = e.currentTarget.dataset.cat;
    if (cat === this.data.activeCat) return;
    this.setData({ activeCat: cat });
  },

  // ===== 清单操作 =====

  addToCart(e) {
    const name = e.currentTarget.dataset.name;
    const cart = this.data.cart;
    cart[name] = (cart[name] || 0) + 1;
    this.setData({ cart });
    this.renderCart();
    wx.showToast({ title: "已添加", icon: "none", duration: 1000 });
  },

  goToRecipe(e) {
    const name = e.currentTarget.dataset.name;
    wx.navigateTo({
      url: "/pages/recipe/recipe?name=" + encodeURIComponent(name)
    });
  },

  increaseQty(e) {
    const name = e.currentTarget.dataset.name;
    const cart = this.data.cart;
    cart[name] = (cart[name] || 0) + 1;
    this.setData({ cart });
    this.renderCart();
  },

  decreaseQty(e) {
    const name = e.currentTarget.dataset.name;
    const cart = this.data.cart;
    if (!cart[name] || cart[name] <= 1) {
      delete cart[name];
    } else {
      cart[name] -= 1;
    }
    this.setData({ cart });
    this.renderCart();
  },

  renderCart() {
    const cart = this.data.cart;
    const menu = this.data.menu;
    let cartList = [];
    let cartCount = 0;

    for (let name in cart) {
      const qty = cart[name];
      if (qty <= 0) continue;
      const dish = menu.find(d => d.name === name);
      if (!dish) continue;
      cartCount += qty;
      cartList.push({ dish_name: name, quantity: qty });
    }

    this.setData({ cartList, cartCount });
  },

  // ===== 备忘 =====

  onNoteInput(e) {
    this.setData({ note: e.detail.value });
  },

  // ===== 保存记录 =====

  submitOrder() {
    if (this.data.cartCount === 0) {
      wx.showToast({ title: "请先选几道菜！", icon: "none" });
      return;
    }

    const cart = this.data.cart;
    const note = this.data.note;
    const orders = [];
    for (let name in cart) {
      if (cart[name] > 0) {
        orders.push({ dish_name: name, quantity: cart[name], note });
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
      wx.showToast({ title: "记录失败", icon: "error" });
    } else {
      wx.showToast({ title: "已记录！", icon: "success" });
      this.setData({ cart: {}, cartList: [], cartCount: 0, note: "" });
    }
  }
});

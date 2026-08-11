const { request, getBase } = require("../../utils/request.js");

const CAT_ICONS = {
  '烧菜': '../../images/cats/shaocai.png',
  '凉菜': '../../images/cats/liangcai.png',
  '汤羹': '../../images/cats/tanggeng.png',
  '主食': '../../images/cats/zhushi.png',
  '小吃': '../../images/cats/xiaochi.png',
  '饮品': '../../images/cats/yinpin.png',
  '热菜': '../../images/cats/rechai.png',
  '蒸菜': '../../images/cats/zhengcai.png',
  '海鲜': '../../images/cats/haixian.png',
  '调料': '../../images/cats/tiaoliao.png'
};
const DEFAULT_ICON = '../../images/cats/default.png';

Page({
  data: {
    apiBase: getBase(),
    menu: [],
    categories: [],
    grouped: {},
    dishList: [],        // 按分类顺序平铺的所有菜品，用于填满右侧空白区域
    scrollTarget: "",    // 点击左侧分类时滚动定位的锚点 id
    loading: true,
    cart: {},
    cartList: [],
    cartCount: 0,
    cartExpanded: false,  // 购物车浮层是否展开明细
    note: "",
    activeCat: "",
    catList: [],
    detailVisible: false,
    detailDish: null,
    placeholder: "../../images/cats/xiaoxia.jpg"
  },

  onLoad() {
    this.loadMenu();
  },

  onShow() {
    this.renderCart();
  },

  async loadMenu() {
    try {
      const res = await request("/menu");
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
      // 平铺所有分类的菜品，每个分类首菜标记 showTitle，并记录分类序号(用于 ascii 锚点 id)
      const catIndexMap = {};
      categories.forEach((c, idx) => { catIndexMap[c] = idx; });
      const dishList = [];
      categories.forEach(c => {
        grouped[c].forEach((d, i) => {
          dishList.push(Object.assign({}, d, {
            showTitle: i === 0,
            catIndex: catIndexMap[c],
            imgLoaded: false,
            imgError: false
          }));
        });
      });
      const catList = categories.map(c => ({
        name: c,
        icon: CAT_ICONS[c] || DEFAULT_ICON
      }));
      this.setData(
        { menu, categories, grouped, dishList, catList, activeCat: categories[0] || "", loading: false },
        () => {
          // 菜单渲染完成后建立滚动联动观察器（替代原来手动测量 + 魔法数字 setTimeout）
          this.observeAnchors();
        }
      );
    } catch (e) {
      // 网络错误由 request 统一弹 Toast，这里只结束 loading
      this.setData({ loading: false });
    }
  },

  // 用 IntersectionObserver 监听各分类锚点相对菜品滚动区的进入/离开，
  // 实现滚动联动高亮。相比手动 measureAnchors + onScroll 算 boundingRect，
  // 它会在图片异步加载导致布局变化时自动重算，无需反复 setTimeout 补测。
  observeAnchors() {
    if (this._io) {
      this._io.disconnect();
      this._io = null;
    }
    const io = wx.createIntersectionObserver(this, { thresholds: [0] });
    this._io = io;
    io.relativeTo(".dish-area").observe(".cat-anchor", (res) => {
      // 某锚点重新进入可视区时，将其对应分类设为高亮（滚动到顶部的那段）
      if (res.intersectionRatio <= 0) return;
      const id = res.id || "";
      if (!id.startsWith("cat")) return;
      const idx = parseInt(id.slice(3), 10);
      const cat = this.data.categories[idx];
      if (cat && cat !== this.data.activeCat) {
        this.setData({ activeCat: cat });
      }
    });
  },

  onImgLoad(e) {
    const idx = e.currentTarget.dataset.idx;
    if (idx !== undefined) {
      this.setData({ ['dishList[' + idx + '].imgLoaded']: true });
    }
    // 图片加载导致高度变化时，IntersectionObserver 会自动重算，无需手动补测
  },

  // 单张菜品图加载失败 → 标记为缺图，改用小夏占位图
  onImgError(e) {
    const idx = e.currentTarget.dataset.idx;
    if (idx !== undefined) {
      this.setData({ ['dishList[' + idx + '].imgError']: true });
    }
  },

  onUnload() {
    if (this._io) this._io.disconnect();
  },

  // ===== 左侧分类切换 =====

  switchCat(e) {
    const cat = e.currentTarget.dataset.cat;
    const idx = this.data.categories.indexOf(cat);
    const target = "cat" + idx;
    this.setData({ activeCat: cat, scrollTarget: "" });
    // 先清空再设置，确保重复点击同一分类也能重新滚动定位
    if (this._scrollTimer) clearTimeout(this._scrollTimer);
    this._scrollTimer = setTimeout(() => {
      this.setData({ scrollTarget: target });
    }, 30);
  },

  // ===== 清单操作 =====

  // 展开/收起购物车明细浮层
  toggleCart() {
    this.setData({ cartExpanded: !this.data.cartExpanded });
  },

  addDish(name) {
    const cart = this.data.cart;
    cart[name] = (cart[name] || 0) + 1;
    this.setData({ cart });
    this.renderCart();
  },

  addToCart(e) {
    const name = e.currentTarget.dataset.name;
    this.addDish(name);
    wx.showToast({ title: "已添加", icon: "none", duration: 1000 });
  },

  // ===== 菜品详情弹层 =====

  openDetail(e) {
    const name = e.currentTarget.dataset.name;
    const dish = this.data.menu.find(d => d.name === name);
    if (!dish) return;
    this.setData({ detailVisible: true, detailDish: dish });
  },

  closeDetail() {
    this.setData({ detailVisible: false });
  },

  onDetailAdd(e) {
    this.addDish(e.detail.name);
    wx.showToast({ title: "已添加", icon: "none", duration: 1000 });
    this.setData({ detailVisible: false });
  },

  onDetailRecipe(e) {
    this.closeDetail();
    this.goToRecipe({ currentTarget: { dataset: { name: e.detail.name } } });
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

  async submitOrder() {
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

    wx.showLoading({ title: "记录中...", mask: true });
    // 并发提交；allSettled 保证即使部分失败也能拿到整体结果，而非中途 reject
    const results = await Promise.allSettled(
      orders.map(o => request("/order", { method: "POST", data: o, showError: false }))
    );
    wx.hideLoading();

    const failed = results.filter(r => r.status === "rejected").length;
    if (failed === 0) {
      wx.showToast({ title: "已生成采购清单", icon: "success" });
      this.setData({ cart: {}, cartList: [], cartCount: 0, note: "", cartExpanded: false });
      // 记录完成后自动跳到采购清单，方便直接买菜
      setTimeout(() => {
        wx.switchTab({ url: "/pages/shopping/shopping" });
      }, 800);
    } else {
      // 部分失败：保留购物车，便于用户重试，避免已成功的记录被「假装成功清空」
      wx.showToast({ title: `有 ${failed} 道菜记录失败`, icon: "none" });
    }
  }
});

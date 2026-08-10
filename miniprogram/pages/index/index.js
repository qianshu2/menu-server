const API = getApp().globalData.apiBase;

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
    apiBase: API,
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
            this.measureAnchors();
            // 图片异步加载会改变布局高度，延迟再测一次，保证滚动高亮准确
            if (this._initMeasure) clearTimeout(this._initMeasure);
            this._initMeasure = setTimeout(() => this.measureAnchors(), 500);
          }
        );
      },
      fail: () => {
        wx.showToast({ title: "加载失败", icon: "error" });
        this.setData({ loading: false });
      }
    });
  },

  // 渲染完成后测量各分类锚点相对菜品区的位置，供滚动联动高亮
  measureAnchors() {
    const q = wx.createSelectorQuery().in(this);
    q.select(".dish-area").boundingClientRect();
    q.selectAll(".cat-anchor").boundingClientRect();
    q.exec((res) => {
      if (!res || !res[0] || !res[1] || !res[1].length) return;
      const viewTop = res[0].top;
      const cats = this.data.categories;
      this._anchors = res[1].map(rect => {
        const idx = parseInt(rect.id.replace(/^cat/, ""), 10);
        return {
          cat: cats[idx] || "",
          index: idx,
          offset: rect.top - viewTop
        };
      });
    });
  },

  // 图片异步加载会改变布局高度，加载完成后重新测量锚点，保证滚动高亮准确
  onImgLoad(e) {
    const idx = e.currentTarget.dataset.idx;
    if (idx !== undefined) {
      this.setData({ ['dishList[' + idx + '].imgLoaded']: true });
    }
    if (this._remeasure) clearTimeout(this._remeasure);
    this._remeasure = setTimeout(() => this.measureAnchors(), 200);
  },

  // 单张菜品图加载失败 → 标记为缺图，改用小夏占位图
  onImgError(e) {
    const idx = e.currentTarget.dataset.idx;
    if (idx !== undefined) {
      this.setData({ ['dishList[' + idx + '].imgError']: true });
    }
  },

  // 滚动时根据可见位置更新左侧高亮分类
  onScroll(e) {
    if (!this._anchors || !this._anchors.length) return;
    const top = e.detail.scrollTop;
    let current = this._anchors[0].cat;
    for (let k = 0; k < this._anchors.length; k++) {
      const a = this._anchors[k];
      if (top >= a.offset - 4) current = a.cat;
      else break;
    }
    if (current !== this.data.activeCat) {
      this.setData({ activeCat: current });
    }
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
      wx.showToast({ title: "已生成采购清单", icon: "success" });
      this.setData({ cart: {}, cartList: [], cartCount: 0, note: "", cartExpanded: false });
      // 记录完成后自动跳到采购清单，方便直接买菜
      setTimeout(() => {
        wx.switchTab({ url: "/pages/shopping/shopping" });
      }, 800);
    }
  }
});

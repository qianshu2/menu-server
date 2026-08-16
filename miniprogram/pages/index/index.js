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

// ===== 时令模块（前端内置，与农历同模式，零部署）=====
// 说明：HTML 原版的「时令蔬菜」很多不在用户 44 道菜库里，
// 这里改为「按季节从真实菜库挑应季菜」，保证点「想吃」都能落到库内菜品。
const SEASON_INFO = {
  spring: { name: '春', veggies: '春笋·菠菜·荠菜·豌豆·韭菜·芹菜' },
  summer: { name: '夏', veggies: '黄瓜·番茄·茄子·冬瓜·空心菜·苦瓜·毛豆·丝瓜' },
  autumn: { name: '秋', veggies: '莲藕·南瓜·山药·芋头·茭白·板栗·秋葵·红薯' },
  winter: { name: '冬', veggies: '白菜·萝卜·胡萝卜·土豆·冬笋·洋葱' }
};
// 每季从 44 道菜中挑选应季/当季更合适的菜（均为库内真实菜品名）
const SEASON_DISHES = {
  spring: ['拍黄瓜', '凉拌木耳', '凉拌三丝', '爽口木耳', '清蒸鲈鱼', '白灼大虾', '爆炒花蛤', '小炒牛肉', '鱼香肉丝', '番茄鸡蛋盖饭', '番茄蛋花汤', '番茄牛腩', '杨枝甘露', '冰镇柠檬水', '凉拌牛肉', '手撕鸡', '笋子牛肉', '口水鸡'],
  summer: ['拍黄瓜', '凉拌木耳', '凉拌三丝', '爽口木耳', '盐水毛豆', '番茄鸡蛋盖饭', '番茄蛋花汤', '番茄牛腩', '酸辣粉', '冰镇柠檬水', '杨枝甘露', '白灼大虾', '清蒸鲈鱼', '爆炒花蛤', '凉拌牛肉', '手撕鸡', '口水鸡', '可乐', '薯条', '炸鸡翅(4个)'],
  autumn: ['红烧肉', '粉蒸肉', '粉蒸排骨', '黄焖鸡', '红烧牛肉', '干锅虾', '辣子鸡丁', '宫保鸡丁', '回锅肉', '酸菜鱼', '毛血旺', '水煮肉片', '海带炖猪脚', '蒜泥白肉', '笋子牛肉', '小炒牛肉', '鱼香肉丝', '银耳莲子羹', '麻婆豆腐', '口水鸡'],
  winter: ['酸萝卜老鸭汤', '海带炖猪脚', '红烧肉', '粉蒸肉', '粉蒸排骨', '黄焖鸡', '红烧牛肉', '水煮肉片', '毛血旺', '辣子鸡丁', '回锅肉', '蒜泥白肉', '麻婆豆腐', '宫保鸡丁', '笋子牛肉', '小炒牛肉', '银耳莲子羹', '番茄牛腩', '酸菜鱼']
};
function getSeasonKey(m) {
  if (m >= 3 && m <= 5) return 'spring';
  if (m >= 6 && m <= 8) return 'summer';
  if (m >= 9 && m <= 11) return 'autumn';
  return 'winter';
}

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
    placeholder: "../../images/cats/xiaoxia.jpg",
    recommend: null,     // 今日推荐菜（按日期确定性选取，同一天不变）
    recImgError: false,  // 推荐菜配图加载失败则回退占位图
    recClosed: false,    // 用户今日是否已关闭推荐（当天不再弹出）
    recommendIsSeasonal: false, // 今日推荐是否落在当季应季菜里
    // 本季时令
    seasonName: '',
    seasonVeggies: '',
    seasonDishes: []
  },

  onLoad() {
    this.restoreCart();
    this.loadMenu();
  },

  onShow() {
    this.renderCart();
  },

  // 恢复上次未提交的购物车（避免杀进程/重进后丢失）
  restoreCart() {
    const cart = wx.getStorageSync("cart") || {};
    this.setData({ cart });
  },

  // 持久化购物车到本地
  persistCart() {
    wx.setStorageSync("cart", this.data.cart);
  },

  async loadMenu(forceRefresh = false) {
    // 先用本地缓存秒开，再后台静默刷新（配合后端 /img 的 1 天缓存头，首屏更快）
    const cache = wx.getStorageSync("menu_cache");
    if (cache && cache.length && !forceRefresh) {
      this.applyMenu(cache);
    }
    try {
      const res = await request("/menu");
      const menu = res.data.data;
      wx.setStorageSync("menu_cache", menu);
      this.applyMenu(menu);
    } catch (e) {
      // 网络错误由 request 统一弹 Toast；若已有缓存渲染则保留，不覆盖为空
      if (!this.data.menu || this.data.menu.length === 0) {
        this.setData({ loading: false });
      }
    }
  },

  // 把菜单按分类分组并渲染（缓存命中与网络刷新共用，避免重复分组逻辑）
  applyMenu(menu) {
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
    // 保留已渲染菜品的图片加载状态，避免刷新时骨架屏闪烁
    const prev = {};
    this.data.dishList.forEach(d => { prev[d.name] = d; });
    const dishList = [];
    categories.forEach(c => {
      grouped[c].forEach((d, i) => {
        const p = prev[d.name];
        dishList.push(Object.assign({}, d, {
          showTitle: i === 0,
          catIndex: catIndexMap[c],
          imgLoaded: p ? p.imgLoaded : false,
          imgError: p ? p.imgError : false
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
        // 菜单就绪后重算购物车计数，确保恢复出的购物车数量正确
        this.renderCart();
        // 菜单就绪后再选今日推荐（依赖完整 menu 数据）
        this.pickRecommend();
        // 菜单就绪后计算当季时令菜
        this.applySeason();
      }
    );
  },

  // ===== 今日推荐 =====

  // 本地日期 YYYY-MM-DD（与 shopping/orders 的 todayStr 同源）
  todayKey() {
    const d = new Date();
    const m = (d.getMonth() + 1).toString().padStart(2, "0");
    const day = d.getDate().toString().padStart(2, "0");
    return `${d.getFullYear()}-${m}-${day}`;
  },

  // 字符串哈希，用于把「日期」换算成稳定的菜品下标
  hashStr(s) {
    let h = 0;
    for (let i = 0; i < s.length; i++) h = (h * 31 + s.charCodeAt(i)) >>> 0;
    return h;
  },

  // 今日推荐：按日期确定性选一道菜。同一天多次刷新结果不变（已缓存），跨天自动换。
  pickRecommend() {
    const menu = this.data.menu;
    if (!menu || menu.length === 0) return;
    const today = this.todayKey();
    // 当日已关闭则不再弹出，跨天（日期变化）后自动恢复
    if (wx.getStorageSync("rec_dismissed") === today) {
      this.setData({ recommend: null, recClosed: true });
      return;
    }
    const cached = wx.getStorageSync("recommend");
    if (cached && cached.date === today && menu.find(d => d.name === cached.name)) {
      this.setData({ recommend: cached.dish, recImgError: false, recClosed: false });
      return;
    }
    const seed = this.hashStr(today);
    const dish = menu[seed % menu.length];
    wx.setStorageSync("recommend", { date: today, name: dish.name, dish });
    this.setData({ recommend: dish, recImgError: false, recClosed: false });
  },

  // 关闭今日推荐：隐藏横幅并记录当日关闭，避免反复打扰
  closeRecommend() {
    this.setData({ recommend: null, recClosed: true });
    wx.setStorageSync("rec_dismissed", this.todayKey());
  },

  // 换一道：随机选一道不同于当前的（菜单≥2 道时才有效）
  reshuffle() {
    if (this.data.recClosed) return;
    const menu = this.data.menu;
    if (!menu || menu.length < 2) return;
    let next = this.data.recommend;
    let guard = 0;
    while (next && next.name === this.data.recommend.name && guard < 20) {
      next = menu[Math.floor(Math.random() * menu.length)];
      guard++;
    }
    this.setData({ recommend: next, recImgError: false });
    this.updateRecSeasonal();
  },

  // 判断当前推荐菜是否落在当季应季菜中（用于显示「时令」标记）
  updateRecSeasonal() {
    const rec = this.data.recommend;
    const names = SEASON_DISHES[getSeasonKey(new Date().getMonth() + 1)] || [];
    this.setData({ recommendIsSeasonal: !!(rec && names.includes(rec.name)) });
  },

  // 计算本季时令：从真实菜库挑当前季节合适的菜，供首页「本季时令」横向展示
  applySeason() {
    const m = new Date().getMonth() + 1;
    const key = getSeasonKey(m);
    const info = SEASON_INFO[key];
    const names = SEASON_DISHES[key] || [];
    const dishes = names
      .map(n => this.data.menu.find(d => d.name === n))
      .filter(Boolean);
    this.setData({
      seasonName: info.name,
      seasonVeggies: info.veggies,
      seasonDishes: dishes
    });
    this.updateRecSeasonal();
  },

  onRecImgError() {
    this.setData({ recImgError: true });
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
    this.persistCart();
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
    this.persistCart();
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
    this.persistCart();
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
      this.persistCart();
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

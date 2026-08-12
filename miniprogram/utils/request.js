// utils/request.js —— 统一请求封装
// 解决 4 个页面重复手写 wx.request、缺少超时、错误处理不一致的问题。
// 用法：const { request, getBase } = require("../../utils/request.js");

function getBase() {
  const app = getApp();
  return (app && app.globalData && app.globalData.apiBase) ||
    "https://menu-server-1-1qs7.onrender.com";
}

/**
 * 发起请求，返回 Promise（resolve 值为 wx.request 的 res 对象，含 data 字段）
 * @param {string} url 相对路径，例如 "/menu"
 * @param {object} [opts]
 * @param {string} [opts.method="GET"]
 * @param {object} [opts.data={}]
 * @param {number} [opts.timeout=8000]
 * @param {boolean} [opts.showError=true] 失败时是否自动弹 Toast
 * @param {number} [opts.retries=1] GET 类请求在「网络层失败」（含 Render 免费版冷启动超时）时自动重试次数；POST 不重试以免重复提交
 */
function request(url, opts = {}) {
  const {
    method = "GET",
    data = {},
    timeout = 8000,
    showError = true,
    retries = 1
  } = opts;
  return new Promise((resolve, reject) => {
    let attempt = 0;
    const run = () => {
      wx.request({
        url: getBase() + url,
        method,
        data,
        timeout,
        success: (res) => {
          // wx.request 仅在网络层失败才走 fail；HTTP 4xx/5xx 仍进 success，
          // 必须手动判定，否则后端报错会被当成功（页面 res.data.data 取空值崩溃）。
          const okStatus = res.statusCode >= 200 && res.statusCode < 300;
          const body = res.data;
          const okBiz = !body || typeof body !== "object" || body.code === undefined || body.code === 200;
          if (okStatus && okBiz) {
            resolve(res);
            return;
          }
          // 业务/HTTP 错误是确定性的，不重试
          const msg = (body && typeof body === "object" && body.msg) ? body.msg : ("请求失败(" + res.statusCode + ")");
          if (showError) {
            wx.showToast({ title: msg, icon: "error" });
          }
          const err = new Error(msg);
          err.statusCode = res.statusCode;
          err.body = body;
          reject(err);
        },
        fail: (err) => {
          // 网络层失败（含超时）：GET 类请求安全重试一次，给 Render 冷启动实例一点时间
          if (method === "GET" && attempt < retries) {
            attempt++;
            setTimeout(run, 600);
            return;
          }
          if (showError) {
            wx.showToast({ title: "网络异常，请稍后重试", icon: "error" });
          }
          reject(err);
        }
      });
    };
    run();
  });
}

module.exports = { request, getBase };

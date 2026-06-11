let accessToken = "";

const sessionStatus = document.querySelector("#sessionStatus");
const meOutput = document.querySelector("#meOutput");
const eventLog = document.querySelector("#eventLog");

function logEvent(message, isError = false) {
  const item = document.createElement("li");
  item.className = isError ? "error" : "";
  item.textContent = `${new Date().toLocaleTimeString()} - ${message}`;
  eventLog.prepend(item);
}

function setSignedIn(signedIn) {
  sessionStatus.textContent = signedIn ? "已登录" : "未登录";
  sessionStatus.classList.toggle("signedIn", signedIn);
}

async function api(path, options = {}) {
  const headers = {
    "Content-Type": "application/json",
    ...(options.headers || {}),
  };

  if (accessToken) {
    headers.Authorization = `Bearer ${accessToken}`;
  }

  const response = await fetch(path, {
    ...options,
    headers,
    credentials: "include",
  });

  const text = await response.text();
  const data = text ? JSON.parse(text) : {};

  if (!response.ok) {
    const detail = data.detail || response.statusText;
    throw new Error(`${response.status} ${detail}`);
  }

  return data;
}

function formValue(id) {
  return document.querySelector(id).value.trim();
}

document.querySelector("#registerForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await api("/auth/register", {
      method: "POST",
      body: JSON.stringify({
        email: formValue("#registerEmail"),
        display_name: formValue("#registerName"),
        password: document.querySelector("#registerPassword").value,
      }),
    });
    logEvent(`注册成功：${data.email}`);
  } catch (error) {
    logEvent(`注册失败：${error.message}`, true);
  }
});

document.querySelector("#loginForm").addEventListener("submit", async (event) => {
  event.preventDefault();
  try {
    const data = await api("/auth/login", {
      method: "POST",
      body: JSON.stringify({
        email: formValue("#loginEmail"),
        password: document.querySelector("#loginPassword").value,
      }),
    });
    accessToken = data.access_token;
    setSignedIn(true);
    logEvent("登录成功，Access Token 已保存在页面内存中");
  } catch (error) {
    logEvent(`登录失败：${error.message}`, true);
  }
});

document.querySelector("#loadMeButton").addEventListener("click", async () => {
  try {
    const data = await api("/auth/me");
    meOutput.textContent = JSON.stringify(data, null, 2);
    logEvent(`读取当前用户成功：${data.email}`);
  } catch (error) {
    logEvent(`读取 /me 失败：${error.message}`, true);
  }
});

document.querySelector("#refreshButton").addEventListener("click", async () => {
  try {
    const data = await api("/auth/refresh", { method: "POST" });
    accessToken = data.access_token;
    setSignedIn(true);
    logEvent("刷新成功，Access Token 已更新");
  } catch (error) {
    logEvent(`刷新失败：${error.message}`, true);
  }
});

document.querySelector("#logoutButton").addEventListener("click", async () => {
  try {
    await api("/auth/logout", { method: "POST" });
    accessToken = "";
    setSignedIn(false);
    meOutput.textContent = "{}";
    logEvent("已登出，Refresh Cookie 已清除");
  } catch (error) {
    logEvent(`登出失败：${error.message}`, true);
  }
});

setSignedIn(false);

const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
const host = window.location.host;
// Функция для получения правильного WebSocket URL в зависимости от контекста
function getWsUrl() {
  const currentPath = window.location.pathname;
  let finalUrl;
  
  // Если мы в Home Assistant ingress (новый формат), используем полный путь
  if (currentPath.includes('/api/hassio_ingress/')) {
    // Убираем trailing slash из currentPath и добавляем /ws
    const basePath = currentPath.endsWith('/') ? currentPath.slice(0, -1) : currentPath;
    finalUrl = `${protocol}//${host}${basePath}/ws`;
    console.log(`[WebSocket] Ingress mode (new): ${finalUrl}`);
  }
  // Если мы в старом формате ingress
  else if (currentPath.includes('/hassio/ingress/')) {
    finalUrl = `${protocol}//${host}/hassio/ingress/local_my_home_devices/ws`;
    console.log(`[WebSocket] Ingress mode (old): ${finalUrl}`);
  }
  // Иначе используем обычный путь
  else {
    finalUrl = `${protocol}//${host}/ws`;
    console.log(`[WebSocket] Direct mode: ${finalUrl}`);
  }
  
  return finalUrl;
}
const wsUrl = getWsUrl();

export class WebSocketService {
  constructor(url) {
    this.url = url;
    this.socket = null;
    this.listeners = new Map();
    this.retryCount = 0;
    this.MAX_RETRIES = 5;
    this.state = 'disconnected';
    this.connect();
  }

  connect() {
    if (!this.socket || this.socket.readyState !== WebSocket.OPEN) {
      this.state = 'connecting';
      this.socket = new WebSocket(this.url);

      this.socket.onopen = () => {
        this.state = 'connected';
        console.info("ws: connected");
        this.retryCount = 0; // Сбросить счётчик при успешном подключении
      };

      this.socket.onmessage = (event) => {
        try {
          const data = JSON.parse(event.data);
          const eventKey = `${data.type}:${data.action || ''}`;
          const payload = data.data || data;
          
          if (this.listeners.has(eventKey)) {
            this.listeners.get(eventKey).forEach((callback) => {
              try {
                callback(payload);
              } catch (error) {
                console.error("Error in WebSocket listener:", error);
              }
            });
          }
        } catch (error) {
          console.error("Error parsing WebSocket message:", error);
        }
      };

      this.socket.onclose = () => {
        this.state = 'disconnected';
        if (this.retryCount < this.MAX_RETRIES) {
          console.warn("ws: disconnected, retrying...");
          this.retryCount++;
          setTimeout(() => this.connect(), 3000 * this.retryCount); // Экспоненциальная задержка
        } else {
          this.state = 'disconnected';
          console.error("ws: disconnected, max retries exceeded");
        }
      };

      this.socket.onerror = (error) => {
        this.state = 'error';
        console.error("ws: error:", error);
        this.socket.close();
      };
    }
  }

  onMessage(group, type, callback) {
    const eventKey = `${group}:${type}`;
    if (!this.listeners.has(eventKey)) {
      this.listeners.set(eventKey, []);
    }
    this.listeners.get(eventKey).push(callback);
  }

  offMessage(group, type, callback) {
    const eventKey = `${group}:${type}`;
    if (this.listeners.has(eventKey)) {
      const callbacks = this.listeners.get(eventKey).filter((cb) => cb !== callback);
      if (callbacks.length > 0) {
        this.listeners.set(eventKey, callbacks);
      } else {
        this.listeners.delete(eventKey);
      }
    }
  }

  send(message) {
    if (this.socket && this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(message);
      console.log('WebSocket message sent:', message);
      return true;
    } else {
      console.warn('WebSocket not connected, cannot send message:', message);
      return false;
    }
  }
}

const webSocketService = new WebSocketService(wsUrl);

export {webSocketService};

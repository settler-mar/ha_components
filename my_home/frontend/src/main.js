import {createApp} from "vue";
import App from "./App.vue";
// import mIcon from '@/components/mIcons.vue';
import {registerPlugins} from "@/plugins";
import {webSocketService} from "./services/websocket.js";


const app = createApp(App);

// app.component('v-icon', mIcon);
// app.component('v-icon', mIcon); // Переопределяем <v-icon>

app.config.globalProperties.$websocket = webSocketService;

app.config.errorHandler = function (err, vm, info) {
  console.log('errorHandler', err, vm, info);
};

registerPlugins(app);
app.mount("#app");

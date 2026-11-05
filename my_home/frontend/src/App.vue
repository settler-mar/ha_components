<template>
  <v-app>
    <!-- Фиксированная навигация -->
    <NavigationBar />

    <v-main style="padding-top: 48px;">
      {{ ha_store }}
      <!-- App messenger -->
      <AppMessenger/>

      <!-- The router view will be rendered here -->
      <router-view/>
    </v-main>
  </v-app>
</template>

<script>
import {mapStores} from "pinia";
import {useHAChangesStore} from '@/store/haChangesStore'
import NavigationBar from './components/NavigationBar.vue'
// const haChangesStore = useHAChangesStore()

export default {
  components: {
    NavigationBar
  },
  computed: {
    ha_store() {
      // return haChangesStore;
    },
  },
  mounted() {
  },
  beforeUnmount() {
    this.$websocket.close();
  },
};
</script>

<style>
.app_bar {
  transition: max-height 0.5s;
  max-height: 100px;
  overflow: hidden;
}

.hide_bar {
  max-height: 0;
}
</style>

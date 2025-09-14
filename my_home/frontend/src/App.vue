<template>
  <v-app>
    <v-main>
      <!-- App messenger -->
      <AppMessenger/>

      <!-- The router view will be rendered here -->
      <router-view/>
    </v-main>
  </v-app>
</template>

<script>
import {mapStores} from "pinia";

export default {
  computed: {
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

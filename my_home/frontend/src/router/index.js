// router/index.ts

import {createRouter, createWebHistory} from "vue-router/auto";

function setMeta(route, parentPath = '') {
  let path = parentPath + ('/' + route.path).replace('//', '/')
  let title = path.split('/').pop().replace(/([A-Z])/g, ' $1').trim().toLocaleLowerCase()
  title = title.charAt(0).toUpperCase() + title.slice(1)
  route.meta = {
    title: title,
  }
  if ('children' in route) {
    route.children = route.children.map(child => setMeta(child, path))
  }
  return route
}

// Функция для определения базового пути в зависимости от контекста
function getBasePath() {
  const currentPath = window.location.pathname;
  let basePath;
  
  // Если мы в Home Assistant ingress, используем полный путь
  if (currentPath.includes('/api/hassio_ingress/')) {
    basePath = currentPath;
    console.log(`[Router] Ingress mode (new): base path = ${basePath}`);
  }
  // Если мы в старом формате ingress
  else if (currentPath.includes('/hassio/ingress/')) {
    basePath = '/hassio/ingress/local_my_home_devices/';
    console.log(`[Router] Ingress mode (old): base path = ${basePath}`);
  }
  // Иначе используем корневой путь
  else {
    basePath = '/';
    console.log(`[Router] Direct mode: base path = ${basePath}`);
  }
  
  return basePath;
}

let router = createRouter({
  history: createWebHistory(getBasePath()),
  extendRoutes(routes) {
    return [
      ...routes.map(route => setMeta(route)),
      {
        path: '/:all(.*)',
        component: () => import('@/views/[...all].vue'),
        meta: {showAppBar: false},
      },
    ]
  }
})


export default router

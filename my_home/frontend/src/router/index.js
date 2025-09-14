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

let router = createRouter({
  history: createWebHistory(),
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

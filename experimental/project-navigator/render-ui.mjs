import {readFile} from 'node:fs/promises';
import {build} from 'esbuild';
import postcss from 'postcss';
import tailwind from '@tailwindcss/postcss';
import {fileURLToPath} from 'node:url';

// Bundle the same renderer and styles used by the original navigator.
export async function renderNavigationUI(){
 const read=p=>readFile(new URL(p,import.meta.url),'utf8');
 const sdk=await build({entryPoints:[fileURLToPath(new URL('./sdk-controls.jsx',import.meta.url))],bundle:true,write:false,outdir:'/tmp/navigation-sdk-bundle',format:'iife',minify:true,define:{'process.env.NODE_ENV':'"production"'},loader:{'.css':'local-css'},logLevel:'silent'});
 const sdkJS=sdk.outputFiles.find(f=>f.path.endsWith('.js')).text;
 const sdkCSS=sdk.outputFiles.find(f=>f.path.endsWith('.css')).text;
 const foundations=await postcss([tailwind()]).process(await read('./sdk.css'),{from:fileURLToPath(new URL('./sdk.css',import.meta.url))});
 const [template,base,content,markdown,icons,renderer]=await Promise.all([
  read('./view.html'),read('../../web/hub.css'),read('../../web/content-page.css'),
  read('../../node_modules/markdown-it/dist/markdown-it.min.js'),read('../../web/hub.js'),read('../../web/content-page.js'),
 ]);
 return template.replace('/* NAVIGATION_STYLES */',()=>foundations.css+'\n@layer base {'+base+'}\n'+content+'\n'+sdkCSS)
  .replace('/* NAVIGATION_SCRIPTS */',()=>[markdown,icons,renderer,sdkJS].join('\n').replace(/<\/script/gi,'<\\/script'));
}

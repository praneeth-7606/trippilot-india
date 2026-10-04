// Real local screen recording: no mocked API responses and no injected UI.
import {chromium} from 'playwright';
import assert from 'node:assert/strict';
import path from 'node:path';

const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||'msedge'});
const context=await browser.newContext({viewport:{width:1280,height:900},
  recordVideo:{dir:path.resolve('../backend/data/demo'),size:{width:1280,height:900}}});
const page=await context.newPage();
const errors=[];page.on('pageerror',e=>errors.push(e.message));
const pause=ms=>page.waitForTimeout(ms);
const started=Date.now();
try{
  await page.goto('http://127.0.0.1:5173');
  await page.getByText('LIVE SEARCH MODE',{exact:false}).waitFor();
  await pause(4000);
  await page.getByRole('button',{name:'Build my road trip'}).click();
  await page.getByRole('heading',{name:'Your journey, mapped out.'}).waitFor({timeout:120000});
  assert.equal((await page.locator('.badge').innerText()).toLowerCase(),'ready');
  await page.locator('.plan-heading').scrollIntoViewIfNeeded();await pause(6000);
  const museum=page.locator('.timeline li').filter({has:page.getByRole('heading',{name:'Tea Museum',exact:true})});
  await museum.scrollIntoViewIfNeeded();await pause(3000);
  await museum.getByText('Sources & estimates',{exact:true}).click();await pause(6000);
  await museum.getByRole('button',{name:'Lock',exact:true}).click();
  await page.getByRole('button',{name:'Unlock',exact:true}).waitFor();await pause(2500);
  await page.getByRole('button',{name:'We’re 90 minutes late'}).click();
  await page.getByText('VERSION 3',{exact:false}).waitFor();
  await page.locator('.warnings').scrollIntoViewIfNeeded();await pause(6000);
  await page.getByText('Route alternatives, costs & weather',{exact:true}).click();
  await page.locator('.support').first().scrollIntoViewIfNeeded();await pause(6000);
  await page.getByText('What didn’t fit & planning assumptions',{exact:true}).click();
  await page.locator('.support').last().scrollIntoViewIfNeeded();await pause(5000);
  await page.evaluate(()=>window.scrollTo({top:0,behavior:'instant'}));await pause(3000);
  assert.deepEqual(errors,[]);
  assert(Date.now()-started<175000,'Recording exceeds demo limit; do not publish it');
  const video=page.video();
  await context.close();
  const file=path.resolve('../docs/trippilot-live-demo.webm');
  await video.saveAs(file);
  console.log(JSON.stringify({recording:file,wall_seconds:Math.round((Date.now()-started)/1000),
    live:true,local:true,page_errors:0}));
}finally{await browser.close();}

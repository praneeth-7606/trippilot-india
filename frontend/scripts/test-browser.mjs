import {chromium} from 'playwright';
import assert from 'node:assert/strict';

const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||undefined});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
const errors=[];
page.on('pageerror',e=>errors.push(e.message));
try{
  await page.goto('http://127.0.0.1:5173');
  await page.getByRole('button',{name:'Build my road trip'}).click();
  await page.getByRole('heading',{name:'Your journey, mapped out.'}).waitFor();
  assert(await page.locator('.timeline li').count()>5);
  assert.equal((await page.locator('.badge').innerText()).toLowerCase(),'ready');
  await page.getByRole('button',{name:'Lock',exact:true}).first().click();
  await page.getByRole('button',{name:'Unlock',exact:true}).waitFor();
  const before=await page.locator('.timeline li.locked .time').innerText();
  await page.getByRole('button',{name:'We’re 90 minutes late'}).click();
  await page.getByText('VERSION 3',{exact:false}).waitFor();
  assert.equal(await page.locator('.timeline li.locked .time').innerText(),before);
  await page.getByRole('button',{name:'Share read-only trip'}).click();
  const shared=page.locator('.share a');await shared.waitFor();
  const url=await shared.getAttribute('href');
  const readOnly=await browser.newPage();await readOnly.goto(url);
  await readOnly.getByRole('heading',{name:'Your journey, mapped out.'}).waitFor();
  assert.equal(await readOnly.getByRole('button',{name:'Lock',exact:true}).count(),0);
  for(const width of [320,768,1024,1440]){
    await page.setViewportSize({width,height:900});
    assert(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth+1),`Overflow at ${width}px`);
  }
  if(process.env.E2E_SCREENSHOT)await page.screenshot({path:process.env.E2E_SCREENSHOT,fullPage:true});
  assert.deepEqual(errors,[]);
  console.log('PASS: plan, lock, delay/version, shared read-only view, 320/768/1024/1440 layouts; no page errors');
}finally{await browser.close();}

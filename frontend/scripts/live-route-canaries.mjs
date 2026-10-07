import {chromium} from 'playwright';

const cases=[
  {origin:'Delhi',destination:'Agra',mode:'car',region:'North'},
  {origin:'Ahmedabad',destination:'Udaipur',mode:'car',region:'West'},
  {origin:'Bengaluru',destination:'Mysuru',mode:'motorcycle',region:'South'},
  {origin:'Kolkata',destination:'Digha',mode:'car',region:'East'},
  {origin:'Guwahati',destination:'Shillong',mode:'motorcycle',region:'North-East'},
];
const browser=await chromium.launch({headless:true,channel:process.env.BROWSER_CHANNEL||undefined});
const page=await browser.newPage({viewport:{width:1440,height:1000}});
page.setDefaultTimeout(90000);
const pageErrors=[];page.on('pageerror',error=>pageErrors.push(error.message));
const results=[];let measuredSearches=0;
try{
  await page.goto('http://127.0.0.1:5173');
  for(const item of cases){
    if(measuredSearches>=100)break;
    await page.getByLabel('Starting point').fill(item.origin);
    await page.getByLabel('Destination').fill(item.destination);
    await page.locator('[name=mode]').selectOption(item.mode);
    await page.locator('[name=start]').fill('2026-11-10');
    await page.locator('[name=return]').fill('2026-11-11');
    await page.getByLabel('Must-visit places').fill('');
    const responsePromise=page.waitForResponse(response=>response.url().includes('/trips/')&&response.url().endsWith('/plan')&&response.request().method()==='POST',{timeout:180000});
    await page.getByRole('button',{name:'Build my road trip'}).click();
    const response=await responsePromise;
    const body=await response.json();
    const version=body.version||{};
    const used=Number(body.search_budget_used||0);measuredSearches+=used;
    results.push({region:item.region,origin:item.origin,destination:item.destination,mode:item.mode,http_status:response.status(),plan_status:version.status||null,distance_km:version.route?.total_distance_km??null,searches_used:used,issue_codes:(version.issues||[]).map(issue=>issue.code)});
  }
  console.log(JSON.stringify({mode:'live SerpApi through actual frontend and backend; per-plan cap 20; aggregate cap 100',count:results.length,measured_searches:measuredSearches,remaining_budget_before:177,results,pageErrors}));
}finally{await browser.close();}

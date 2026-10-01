import { test, expect } from '@playwright/test';

test('broker case: review, approved mock filing and clock',async({page,context})=>{
  await page.goto('/');
  await page.getByRole('button',{name:/Broker grievance .*My withdrawal/}).click();
  await page.getByRole('button',{name:'Review facts',exact:true}).click();
  await page.getByRole('button',{name:'Confirm facts & prepare complaint'}).click();
  await page.getByRole('button',{name:'Review & simulate filing'}).click();
  await expect(page.getByRole('button',{name:'Approve simulated submission'})).toBeDisabled();
  const href=await page.getByRole('link',{name:'Open the demo form portal'}).getAttribute('href');
  const portal=await context.newPage();
  await portal.goto(href!);
  await expect(portal.getByLabel('Prepared complaint')).toHaveValue(/Request for assistance/);
  await expect(portal.getByRole('button',{name:'Submit simulation'})).toBeDisabled();
  await portal.getByRole('checkbox',{name:'I approve this demo submission'}).check();
  await portal.getByRole('button',{name:'Submit simulation'}).click();
  await expect(portal.getByTestId('reference')).toContainText('DEMO-');
});

test('mobile dashboard has no horizontal overflow',async({page})=>{
  await page.setViewportSize({width:390,height:844});
  await page.goto('/');
  await expect(page.getByRole('heading',{name:'Your next step, made clear.'})).toBeVisible();
  expect(await page.evaluate(()=>document.documentElement.scrollWidth<=window.innerWidth)).toBeTruthy();
});

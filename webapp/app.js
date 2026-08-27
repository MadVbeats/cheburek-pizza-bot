const tg = window.Telegram?.WebApp;
if (tg) {
  tg.expand();
  tg.enableClosingConfirmation();
  tg.ready();
}

let menu = {};
let categories = [];
let activeCat = 0;
// cart: Map "ci:ii" -> qty
const cart = new Map();

const catsEl = document.getElementById('cats');
const itemsEl = document.getElementById('items');
const cartBar = document.getElementById('cartBar');
const cartCountEl = document.getElementById('cartCount');
const cartTotalEl = document.getElementById('cartTotal');
const modal = document.getElementById('modal');
const modalBackdrop = document.getElementById('modalBackdrop');
const closeModalBtn = document.getElementById('closeModalBtn');
const openCartBtn = document.getElementById('openCartBtn');
const cartLinesEl = document.getElementById('cartLines');
const modalTotalEl = document.getElementById('modalTotal');
const orderForm = document.getElementById('orderForm');
const nameEl = document.getElementById('name');
const phoneEl = document.getElementById('phone');
const addressEl = document.getElementById('address');
const formHint = document.getElementById('formHint');
const submitBtn = document.getElementById('submitBtn');

let method = 'pickup';
document.querySelectorAll('.method-btn').forEach(btn=>{
  btn.addEventListener('click', ()=>{
    document.querySelectorAll('.method-btn').forEach(b=>b.classList.remove('active'));
    btn.classList.add('active');
    method = btn.dataset.method;
    addressEl.classList.toggle('hidden', method!=='delivery');
    if(method==='delivery') addressEl.required = true; else addressEl.required = false;
    if(tg?.HapticFeedback) tg.HapticFeedback.selectionChanged();
  });
});

function toast(msg){
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.classList.remove('hidden');
  setTimeout(()=>el.classList.add('hidden'), 2500);
}

function cartKey(ci,ii){ return `${ci}:${ii}`; }
function getQty(ci,ii){ return cart.get(cartKey(ci,ii))||0; }
function setQty(ci,ii,qty){
  const k = cartKey(ci,ii);
  if(qty<=0) cart.delete(k); else cart.set(k, qty);
  renderItems();
  renderCartBar();
  if(tg?.HapticFeedback) tg.HapticFeedback.impactOccurred('light');
}
function cartStats(){
  let count=0, total=0;
  for(const [k,qty] of cart){
    const [ci,ii]=k.split(':').map(Number);
    const item = menu[categories[ci]][ii];
    total += item.price * qty;
    count += qty;
  }
  return {count, total};
}

async function loadMenu(){
  const res = await fetch('/api/menu');
  const data = await res.json();
  menu = data.menu;
  categories = data.categories;
  activeCat = 0;
  renderCats();
  renderItems();
}

function renderCats(){
  catsEl.innerHTML='';
  categories.forEach((cat, idx)=>{
    const b = document.createElement('button');
    b.className = 'cat-btn'+(idx===activeCat?' active':'');
    b.textContent = cat;
    b.onclick = ()=>{ activeCat=idx; renderCats(); renderItems(); };
    catsEl.appendChild(b);
  });
}

function renderItems(){
  itemsEl.innerHTML='';
  const cat = categories[activeCat];
  const items = menu[cat]||[];
  items.forEach((item, ii)=>{
    const ci = activeCat;
    const qty = getQty(ci,ii);
    const card = document.createElement('div');
    card.className='card';
    card.innerHTML = `
      <div class="card-top"><span class="card-name">${item.name}</span><span class="price">${item.price} ₽</span></div>
      ${item.desc?`<div class="card-desc">${item.desc}</div>`:''}
      <div class="card-bottom">
        <span class="hint">${item.weight||''}</span>
        <div class="qty-row">
          ${qty>0?`<button class="q-btn" data-act="dec">−</button><span class="qty">${qty}</span><button class="q-btn" data-act="inc">+</button>`:`<button class="add-btn">Добавить</button>`}
        </div>
      </div>
    `;
    const dec = card.querySelector('[data-act="dec"]');
    const inc = card.querySelector('[data-act="inc"]');
    const add = card.querySelector('.add-btn');
    if(dec) dec.onclick = ()=> setQty(ci,ii,qty-1);
    if(inc) inc.onclick = ()=> setQty(ci,ii,qty+1);
    if(add) add.onclick = ()=> setQty(ci,ii,1);
    itemsEl.appendChild(card);
  });
}

function renderCartBar(){
  const {count, total} = cartStats();
  if(count===0){ cartBar.classList.add('hidden'); return; }
  cartBar.classList.remove('hidden');
  cartCountEl.textContent = `${count} ${count===1?'позиция':count<5?'позиции':'позиций'}`;
  cartTotalEl.textContent = `${total} ₽`;
  if(tg?.MainButton){
    tg.MainButton.setText(`Оформить · ${total} ₽`);
    tg.MainButton.show();
  }
}

function renderCartModal(){
  cartLinesEl.innerHTML='';
  let total=0;
  if(cart.size===0){
    cartLinesEl.innerHTML='<p class="hint">Корзина пуста</p>';
  }
  for(const [k,qty] of cart){
    const [ci,ii]=k.split(':').map(Number);
    const item = menu[categories[ci]][ii];
    const sum = item.price * qty;
    total += sum;
    const row = document.createElement('div');
    row.className='cart-line';
    row.innerHTML = `
      <span>${item.name}</span>
      <div class="qty-row">
        <button class="q-btn" data-act="dec">−</button>
        <span class="qty">${qty}</span>
        <button class="q-btn" data-act="inc">+</button>
        <span style="min-width:70px;text-align:right;font-weight:700">${sum} ₽</span>
      </div>
    `;
    row.querySelector('[data-act="dec"]').onclick=()=>{ setQty(ci,ii,qty-1); renderCartModal(); };
    row.querySelector('[data-act="inc"]').onclick=()=>{ setQty(ci,ii,qty+1); renderCartModal(); };
    cartLinesEl.appendChild(row);
  }
  modalTotalEl.textContent = total+' ₽';
}

function openModal(){
  if(cart.size===0){ toast('Корзина пуста'); return; }
  renderCartModal();
  modal.classList.remove('hidden');
  document.body.style.overflow='hidden';
}
function closeModal(){
  modal.classList.add('hidden');
  document.body.style.overflow='';
}

openCartBtn.onclick = openModal;
modalBackdrop.onclick = closeModal;
closeModalBtn.onclick = closeModal;

if(tg?.MainButton){
  tg.MainButton.onClick(openModal);
}
if(tg?.BackButton){
  // optional
}

orderForm.onsubmit = async (e)=>{
  e.preventDefault();
  const name = nameEl.value.trim();
  const phone = phoneEl.value.trim();
  const address = addressEl.value.trim();
  if(name.length<2){ formHint.textContent='Введите имя'; return; }
  if(!/^\+?\d[\d\s\-()]{8,18}$/.test(phone)){ formHint.textContent='Неверный телефон'; return; }
  if(method==='delivery' && address.length<5){ formHint.textContent='Укажите адрес'; return; }
  if(cart.size===0){ formHint.textContent='Корзина пуста'; return; }

  submitBtn.disabled=true;
  submitBtn.textContent='Отправка...';
  formHint.textContent='';

  const cartArr = [...cart].map(([k,qty])=>{
    const [ci,ii]=k.split(':').map(Number);
    return {ci, ii, qty};
  });

  try{
    const res = await fetch('/api/order', {
      method:'POST',
      headers:{'Content-Type':'application/json'},
      body: JSON.stringify({
        initData: tg?.initData || '',
        name, phone, method, address,
        cart: cartArr
      })
    });
    const data = await res.json();
    if(!res.ok) throw new Error(data.detail || 'Ошибка');
    cart.clear();
    renderCartBar();
    renderItems();
    closeModal();
    // success screen
    itemsEl.innerHTML = `<div class="card" style="text-align:center;padding:24px"><h2>✅ Заказ №${data.order_id} принят!</h2><p>Мы позвоним для подтверждения.</p><p style="font-size:20px">Итого: <b>${data.total} ₽</b></p><button class="btn btn-primary" onclick="location.reload()">К меню</button></div>`;
    window.scrollTo(0,0);
    if(tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('success');
    if(tg) tg.MainButton.hide();
    toast('Заказ отправлен!');
  }catch(err){
    formHint.textContent = 'Ошибка: '+ err.message;
    if(tg?.HapticFeedback) tg.HapticFeedback.notificationOccurred('error');
  }finally{
    submitBtn.disabled=false;
    submitBtn.textContent='✅ Оформить заказ';
  }
};

loadMenu().catch(()=> toast('Не удалось загрузить меню'));

(function(){
  try {
    const key = 'lang';
    const stored = window.localStorage.getItem(key);
    const current = (stored === 'en' || stored === 'ru') ? stored : 'ru';
    document.documentElement.lang = current;
  } catch (e) {}
})();

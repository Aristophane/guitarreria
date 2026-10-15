/* City-level locations, documented in geography.json. No external map requests. */
(async () => {
  const host = document.querySelector('#makers-map');
  if (!host || !window.L) return;
  const status = document.querySelector('#geography-status');
  const heading = document.querySelector('#directory-heading');
  const entries = [...document.querySelectorAll('[data-directory-entry]')];
  const buttons = [...document.querySelectorAll('[data-country]')];
  try {
    const responses = await Promise.all(['geography.json', 'assets/map/world.geojson'].map(url => fetch(url)));
    if (responses.some(response => !response.ok)) throw new Error('map-data');
    const [data, world] = await Promise.all(responses.map(response => response.json()));
    const points = data.flatMap(maker => (maker.locations?.length ? maker.locations : [maker]).filter(place => Number.isFinite(place.lat) && Number.isFinite(place.lon)).map(place => ({...maker, ...place})));
    const map = L.map(host, {scrollWheelZoom: false, minZoom: 0, maxZoom: 8, zoomSnap: .25, maxBounds: [[-65,-190],[85,190]], maxBoundsViscosity: .8});
    map.attributionControl.setPrefix(false);
    map.attributionControl.addAttribution('<a href="https://www.naturalearthdata.com/">Natural Earth</a> · <a href="https://leafletjs.com/">Leaflet</a>');
    const represented = new Set(points.map(point => point.country));
    const countries = {'France':'France','Spain':'Espagne','Belgium':'Belgique','Netherlands':'Pays-Bas','Greece':'Grèce','Germany':'Allemagne','Russia':'Russie','South Africa':'Afrique du Sud','United States of America':'États-Unis','Italy':'Italie','Canada':'Canada','United Kingdom':'Royaume-Uni'};
    L.geoJSON(world, {style: feature => ({color:'#55574d', weight:.6, fillColor:represented.has(countries[feature.properties.ADMIN]) ? '#4e4738' : '#30342e', fillOpacity:1}), onEachFeature: (feature, layer) => layer.bindTooltip(countries[feature.properties.ADMIN] || feature.properties.NAME_FR || feature.properties.ADMIN, {sticky:true, className:'map-tooltip'})}).addTo(map);
    const markers = L.layerGroup().addTo(map);
    let active = points;
    function selectRoutes(routes, label) {
      const selected = new Set(routes);
      let count = 0;
      entries.forEach(entry => {entry.hidden = !selected.has(entry.dataset.route); if (!entry.hidden) count++;});
      heading.textContent = label;
      status.textContent = `${count} / ${data.length} luthiers`;
    }
    function renderMarkers() {
      markers.clearLayers();
      const groups = [];
      for (const point of active) {
        const position = map.latLngToLayerPoint([point.lat,point.lon]);
        const group = groups.find(group => position.distanceTo(group.position) < 38);
        if (group) group.points.push(point); else groups.push({position,points:[point]});
      }
      groups.forEach(group => {
        const unique = [...new Set(group.points.map(point => point.route))];
        const cities = [...new Set(group.points.map(point => point.city))];
        const label = cities.length === 1 ? `${cities[0]} · ${unique.length} ${unique.length === 1 ? 'luthier' : 'luthiers'}` : `${unique.length} luthiers · ${cities.length} villes`;
        const historical = group.points.every(point => point.status === 'historical');
        const uncertain = group.points.every(point => point.status === 'uncertain');
        const marker = L.marker([group.points.reduce((sum,p)=>sum+p.lat,0)/group.points.length,group.points.reduce((sum,p)=>sum+p.lon,0)/group.points.length], {icon:L.divIcon({className:`maker-map-marker${historical?' is-historical':''}${uncertain?' is-uncertain':''}`,html:`<span>${unique.length}</span>`,iconSize:[36,36],iconAnchor:[18,18]}),title:label,alt:label,keyboard:true,riseOnHover:true});
        marker.bindTooltip(label, {direction:'top',className:'map-tooltip'});
        marker.on('click', () => {
          selectRoutes(unique, cities.length === 1 ? cities[0] : 'Luthiers de cette région');
          if (cities.length > 1 && map.getZoom() < 7) map.fitBounds(group.points.map(point=>[point.lat,point.lon]), {padding:[65,65],maxZoom:7,animate:false});
          document.querySelector('#map-selection').textContent = cities.length === 1 ? `${cities[0]} — ${group.points[0].country}` : 'Sélection sur la carte';
          document.querySelector('#map-selection').focus({preventScroll:true});
        });
        marker.on('add',()=> {
          const element = marker.getElement();
          if (!element) return;
          element.setAttribute('aria-label',label);
          element.addEventListener('keydown',event=> {
            if (event.key === 'Enter' || event.key === ' ') {
              event.preventDefault(); event.stopPropagation(); marker.fire('click');
            }
          });
        });
        marker.addTo(markers);
      });
    }
    function worldView() {map.fitBounds([[-60,-180],[80,180]], {padding:[15,15],animate:false});}
    function countryView(country) {
      active = country ? points.filter(point=>point.country === country) : points;
      const routes = country ? data.filter(maker=>(maker.locations || [maker]).some(place=>place.country === country)).map(maker=>maker.route) : data.map(maker=>maker.route);
      selectRoutes(routes, country || 'Tous les luthiers');
      buttons.forEach(button => button.setAttribute('aria-pressed',String(button.dataset.country === country)));
      document.querySelector('#map-selection').textContent = country || 'Monde';
      if (!country || !active.length) worldView();
      else map.fitBounds(active.map(point=>[point.lat,point.lon]), {padding:[65,65],maxZoom:6,animate:false});
      renderMarkers();
    }
    buttons.forEach(button=>button.addEventListener('click',()=>countryView(button.dataset.country)));
    document.querySelector('[data-world]').addEventListener('click',()=>countryView(''));
    document.querySelector('[data-show-all]').addEventListener('click',()=>countryView(''));
    document.querySelectorAll('[data-locate]').forEach(button=>button.addEventListener('click',()=> {
      const point = points.find(point=>point.route===button.dataset.locate);
      if (!point) return;
      active = points;
      buttons.forEach(button=>button.setAttribute('aria-pressed','false'));
      map.setView([point.lat,point.lon],7,{animate:false});
      renderMarkers();
      selectRoutes(points.filter(p=>p.city===point.city && p.country===point.country).map(p=>p.route),point.city);
      document.querySelector('#map-selection').textContent = `${point.city} — ${point.country}`;
      host.scrollIntoView({behavior:'instant',block:'center'});
      host.focus({preventScroll:true});
    }));
    map.on('zoomend', renderMarkers);
    new ResizeObserver(()=>map.invalidateSize()).observe(host);
    countryView('');
    document.querySelector('.map-loading').hidden = true;
  } catch (error) {
    document.querySelector('.map-loading').textContent = 'Carte indisponible. Les localisations et leurs sources restent dans la liste ci-dessous.';
  }
})();

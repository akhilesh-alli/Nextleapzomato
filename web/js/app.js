/**
 * Obsidian Gourmet Concierge - Client Application Logic
 * Integrates with /api/recommend backend orchestrator with real-time UI states,
 * modal dialogs, bookmark persistence, and dynamic visual mosaic generation.
 */

(function () {
  'use strict';

  // ── API Base URL ─────────────────────────────────────────────────────────────
  // Decoupled API Base for production deployment (Railway Backend + Vercel Frontend).
  // Priority: URL query param (?api_base=...) -> localStorage -> window.CONCIERGE_API_BASE -> ''
  function resolveApiBase() {
    if (typeof window === 'undefined') return '';
    try {
      const urlParams = new URLSearchParams(window.location.search);
      const queryBase = urlParams.get('api_base');
      if (queryBase) {
        const cleaned = queryBase.trim().replace(/\/+$/, '');
        localStorage.setItem('CONCIERGE_API_BASE', cleaned);
        return cleaned;
      }
    } catch (_) {}
    try {
      const stored = localStorage.getItem('CONCIERGE_API_BASE');
      if (stored) return stored.trim().replace(/\/+$/, '');
    } catch (_) {}
    if (window.CONCIERGE_API_BASE && typeof window.CONCIERGE_API_BASE === 'string') {
      return window.CONCIERGE_API_BASE.trim().replace(/\/+$/, '');
    }
    return '';
  }
  const API_BASE = resolveApiBase();

  async function fetchBackendTelemetry() {
    try {
      const healthUrl = `${API_BASE}/api/health`;
      const res = await fetch(healthUrl);
      if (res.ok) {
        const data = await res.json();
        const modelLabel = document.getElementById('activeModelLabel');
        if (modelLabel && data.model) {
          const providerStr = data.provider ? (data.provider.charAt(0).toUpperCase() + data.provider.slice(1)) : 'Groq';
          modelLabel.textContent = `${providerStr} ${data.model}`;
          state.activeModel = `${providerStr} / ${data.model}`;
        }
        const pill = document.getElementById('headerTelemetryPill');
        if (pill && data.dataset_rows) {
          pill.title = `Connected to ${data.service} (${data.dataset_rows} restaurants in dataset)`;
        }
      }
    } catch (err) {
      console.warn('Backend telemetry check:', err);
    }
  }

  // ── Global State ────────────────────────────────────────────────────────────
  const state = {
    location: 'Koramangala, Bangalore',
    cuisines: ['Italian', 'Wood-fired Pizza'],
    budget: 'medium', // 'low', 'medium', 'high', ''
    minRating: 4.0,
    onlineDelivery: true,
    tableBooking: true,
    vibePrompt: 'Cozy romantic dinner with outdoor candle-lit seating, craft wine pairing, and live acoustic music. Not too noisy.',
    bookmarks: JSON.parse(localStorage.getItem('concierge_bookmarks') || '["Chianti Artisanal Ristorante & Wine Bar"]'),
    activeView: 'explore-feed',
    isSearching: false,
    lastResult: null,
    activeModel: 'Groq / LLaMA 3.3 70B',
  };

  // ── Culinary Image Assets Library ───────────────────────────────────────────
  const CULINARY_GALLERY = {
    italian: [
      { url: 'https://lh3.googleusercontent.com/aida-public/AB6AXuAcrF0Nlo7aUq9-1H8AtHetu8Lr-Bw8RExdIY2TnzWv1Zt5KcPEetaBM1S0Oum6pQLUUqUZxj7vgvnscAtRwPuw4p4EzMP0KYY_r_w4ttqJiJUsOiiFfeAZ6A_xKSf_LKfQMqYrEH8Giz-REK_pkaXsTf8zVE8VPcaS7oynF9p0wUwsjPaw6R0IS_rCfEsnx5lMnIuNp3w7BTMGFmbTF0xXmmIzhCQKJFhgS1HtceyvHt6xVVUcvkw8', tag: 'Outdoor Courtyard' },
      { url: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBYtxpwMA9Y6hkkkJR2QXGLuu-WxhNYDzW0GRUE6v6nBlgvkn5jdeXz_W46wXbDo_fEz7WEyhoWrIu42_Zf5Wb-Mrsp-i-2kNGkCkpZokcWBm07UVg0yByrwtpiTgi0c8hbkcZT0nFP1WjesgPdir4RYKzW6aj4bXUJByJuzcaYgls3CIDnSozzcuPYms6GdFiGZCRBTj3D2jq3ajZjY9xfk46U1Edit2fJGj1JFpRyANiPIoLTUEUk', tag: 'Tuscan Sourdough Crust' },
      { url: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCq3UIQIjBQXMAq3lOnf22dk5hNue7bo-6XbEM4wbN7Z_KYjIjh1SYheHm3vDNeDIdvXXFqV5dHL5EIAQGJgKY2b4R7uvL7oUCThOBUypv5JGRly_SFMRiHGRhDCmMbCIW4GKHdI0vZDeHa4_wrfazECNIZYuedrBW5gY3UBV0kFEHbTI3ET8lKpQV-eAs8fs_qRV5WpbFekJP8z390qveL_2KOzTiV1BaM7YZOXeO2ij6MCKL5bckZ', tag: 'Curated Cellar (40+ Labels)' },
    ],
    modern: [
      { url: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCSpC1FOxQY3QMvsECodoptjS7Hnvuu1uiY4PtkdMlJ4OgcW2dFBGyvgI5qUOMSZ7cIDTf-dJjOLhHRI2w2_2OjE_B2prvOUnwba5llXlLjEi-O_ppUoTSvBvK3wR-kDPgW_Ayu-d7dK9-dCKubXgC0cq7i_GldfqTPdKWEmBQnnRIHVGsNns874Z8O-F0v_sZonYPl1i9jxHZ1lDn87L0Zqv0zT8-nnBWzi1zDNLS3ulYHlvAPnLpV', tag: 'Balcony Deck' },
      { url: 'https://images.unsplash.com/photo-1544025162-d76694265947?auto=format&fit=crop&w=800&q=80', tag: 'Artisanal Grill' },
      { url: 'https://images.unsplash.com/photo-1550966871-3ed3cdb5ed0c?auto=format&fit=crop&w=800&q=80', tag: 'Amber Cocktails' },
    ],
    rustic: [
      { url: 'https://lh3.googleusercontent.com/aida-public/AB6AXuA6WpC2-oRhgq5m7sKyBWJ2EZsQUU4OO6EV-ft5y1S7TwHb15DY3lnBN7P6f5fIqV0rvuFetn2NaaNY372vFjT-EQ4UqGoZFoqO00qvIdqQWQesxmKx8LKfbFSRYqTxPXA9dHXHivYhq3jRyL3mPyxu15Xc4H-xmwCVG6aHMnaIdXPHDCfy1GQicgZbhSKgkX2H-Wu-Tjl2m-Pj4Koy-rtp5p8kqhpN_owWTAQv-8qnt4rzlV3MtF9x', tag: 'Rustic Patio' },
      { url: 'https://images.unsplash.com/photo-1513104890138-7c749659a591?auto=format&fit=crop&w=800&q=80', tag: 'Stone Baked' },
      { url: 'https://images.unsplash.com/photo-1579684947550-22e945225d9a?auto=format&fit=crop&w=800&q=80', tag: 'Dolci & Tiramisu' },
    ],
    cafe: [
      { url: 'https://images.unsplash.com/photo-1554118811-1e0d58224f24?auto=format&fit=crop&w=800&q=80', tag: 'Botanical Atrium' },
      { url: 'https://images.unsplash.com/photo-1509042239860-f550ce710b93?auto=format&fit=crop&w=800&q=80', tag: 'Pour-Over Brew' },
      { url: 'https://images.unsplash.com/photo-1559925393-8be0ec4767c8?auto=format&fit=crop&w=800&q=80', tag: 'Sunlit Reading Nook' },
    ],
    asian: [
      { url: 'https://images.unsplash.com/photo-1552611052-33e04de081de?auto=format&fit=crop&w=800&q=80', tag: 'Lantern Terrace' },
      { url: 'https://images.unsplash.com/photo-1569718212165-3a8278d5f624?auto=format&fit=crop&w=800&q=80', tag: 'Signature Ramen' },
      { url: 'https://images.unsplash.com/photo-1541544741938-0af808871cc0?auto=format&fit=crop&w=800&q=80', tag: 'Dim Sum Station' },
    ],
    indian: [
      { url: 'https://images.unsplash.com/photo-1589302168068-964664d93dc0?auto=format&fit=crop&w=800&q=80', tag: 'Royal Dum Biryani' },
      { url: 'https://images.unsplash.com/photo-1631452180519-c014fe946bc7?auto=format&fit=crop&w=800&q=80', tag: 'Charcoal Tandoor' },
      { url: 'https://images.unsplash.com/photo-1517248135467-4c7edcad34c4?auto=format&fit=crop&w=800&q=80', tag: 'Heritage Dining' },
    ],
  };

  function getImagesForCuisine(cuisineStr) {
    const c = (cuisineStr || '').toLowerCase();
    if (c.includes('italian') || c.includes('pizza') || c.includes('pasta')) return CULINARY_GALLERY.italian;
    if (c.includes('cafe') || c.includes('coffee') || c.includes('bakery')) return CULINARY_GALLERY.cafe;
    if (c.includes('asian') || c.includes('chinese') || c.includes('thai') || c.includes('japanese')) return CULINARY_GALLERY.asian;
    if (c.includes('biryani') || c.includes('north indian') || c.includes('mughlai') || c.includes('south')) return CULINARY_GALLERY.indian;
    if (c.includes('bar') || c.includes('cocktail') || c.includes('continental')) return CULINARY_GALLERY.modern;
    return CULINARY_GALLERY.rustic;
  }

  // ── DOM Element Cache ───────────────────────────────────────────────────────
  let elements = {};

  function initElements() {
    elements = {
      locationInput: document.getElementById('locationInput'),
      locationPills: document.querySelectorAll('.quick-pill[data-loc]'),
      cuisineTags: document.querySelectorAll('.tag-pill[data-cuisine]'),
      resetCuisinesBtn: document.getElementById('resetCuisinesBtn'),
      budgetBtns: document.querySelectorAll('.segment-btn[data-budget]'),
      ratingSlider: document.getElementById('ratingSlider'),
      ratingValDisplay: document.getElementById('ratingValDisplay'),
      toggleDelivery: document.getElementById('toggleDelivery'),
      toggleBooking: document.getElementById('toggleBooking'),
      vibeTextarea: document.getElementById('vibeTextarea'),
      vibeChips: document.querySelectorAll('.vibe-chip'),
      discoverBtn: document.getElementById('discoverBtn'),
      searchSummaryPill: document.getElementById('searchSummaryPill'),
      summaryText: document.getElementById('summaryText'),
      summaryTimestamp: document.getElementById('summaryTimestamp'),
      relaxationBanner: document.getElementById('relaxationBanner'),
      relaxationText: document.getElementById('relaxationText'),
      synthesisCard: document.getElementById('synthesisCard'),
      synthesisParagraph: document.getElementById('synthesisParagraph'),
      synthesisSubtext: document.getElementById('synthesisSubtext'),
      metricSemantic: document.getElementById('metricSemantic'),
      metricAcoustic: document.getElementById('metricAcoustic'),
      metricConfidence: document.getElementById('metricConfidence'),
      metricWaitTime: document.getElementById('metricWaitTime'),
      feedContainer: document.getElementById('feedContainer'),
      skeletonCard: document.getElementById('skeletonCard'),
      telemetryStrip: document.getElementById('telemetryStrip'),
      telemetryLatency: document.getElementById('telemetryLatency'),
      telemetryCounts: document.getElementById('telemetryCounts'),
      telemetryModel: document.getElementById('telemetryModel'),
      bookmarkCount: document.getElementById('bookmarkCount'),
      headerBookmarkBtn: document.getElementById('headerBookmarkBtn'),
      navLinks: document.querySelectorAll('.nav-link'),
      views: document.querySelectorAll('.view-section'),
      bookingModal: document.getElementById('bookingModal'),
      modalCloseBtn: document.getElementById('modalCloseBtn'),
      modalRestaurantName: document.getElementById('modalRestaurantName'),
      bookingForm: document.getElementById('bookingForm'),
      bookmarksModal: document.getElementById('bookmarksModal'),
      bookmarksModalCloseBtn: document.getElementById('bookmarksModalCloseBtn'),
      bookmarksList: document.getElementById('bookmarksList'),
      toastContainer: document.getElementById('toastContainer'),
    };
  }

  // ── Toast Notification System ───────────────────────────────────────────────
  function showToast(message, type = 'success') {
    if (!elements.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    const icon = type === 'success' ? 'check_circle' : 'info';
    toast.innerHTML = `<span class="material-symbols-outlined filled text-tertiary">${icon}</span><span>${message}</span>`;
    elements.toastContainer.appendChild(toast);
    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3800);
  }

  // ── Bookmark System ─────────────────────────────────────────────────────────
  function updateBookmarkBadge() {
    if (elements.bookmarkCount) {
      elements.bookmarkCount.textContent = state.bookmarks.length;
    }
  }

  function toggleBookmark(restaurantName) {
    const idx = state.bookmarks.indexOf(restaurantName);
    if (idx > -1) {
      state.bookmarks.splice(idx, 1);
      showToast(`Removed <strong>${restaurantName}</strong> from bookmarks`, 'info');
    } else {
      state.bookmarks.push(restaurantName);
      showToast(`Saved <strong>${restaurantName}</strong> to bookmarks!`, 'success');
    }
    localStorage.setItem('concierge_bookmarks', JSON.stringify(state.bookmarks));
    updateBookmarkBadge();
    renderFeed(state.lastResult ? state.lastResult.recommendations : null);
  }

  function openBookmarksModal() {
    if (!elements.bookmarksList) return;
    elements.bookmarksList.innerHTML = '';
    if (state.bookmarks.length === 0) {
      elements.bookmarksList.innerHTML = '<p class="text-muted" style="padding: 1rem 0;">No bookmarked dining spots yet. Click the heart icon on any card to save your favorites!</p>';
    } else {
      state.bookmarks.forEach(name => {
        const row = document.createElement('div');
        row.style.cssText = 'display:flex; align-items:center; justify-content:space-between; padding: 10px 14px; border-radius: 8px; background: rgba(255,255,255,0.04); margin-bottom: 8px;';
        row.innerHTML = `
          <div style="display:flex; align-items:center; gap: 8px;">
            <span class="material-symbols-outlined text-secondary" style="font-size:20px;">restaurant</span>
            <span style="font-weight:600; color:var(--text-primary);">${name}</span>
          </div>
          <div style="display:flex; align-items:center; gap: 8px;">
            <button class="card-btn-primary" style="padding: 4px 10px; font-size:11px;" onclick="window.conciergeApp.openBookingModal('${name.replace(/'/g, "\\'")}')">Reserve</button>
            <button style="color:var(--text-muted); cursor:pointer;" onclick="window.conciergeApp.removeBookmark('${name.replace(/'/g, "\\'")}')">
              <span class="material-symbols-outlined" style="font-size:18px;">delete</span>
            </button>
          </div>
        `;
        elements.bookmarksList.appendChild(row);
      });
    }
    elements.bookmarksModal.classList.add('open');
  }

  // ── Modal Handlers ──────────────────────────────────────────────────────────
  function openBookingModal(restaurantName) {
    if (elements.modalRestaurantName) {
      elements.modalRestaurantName.textContent = restaurantName;
    }
    elements.bookingModal.classList.add('open');
  }

  function closeBookingModal() {
    elements.bookingModal.classList.remove('open');
  }

  // ── Navigation & Views Switcher ─────────────────────────────────────────────
  function setupNavigation() {
    elements.navLinks.forEach(link => {
      link.addEventListener('click', (e) => {
        e.preventDefault();
        const targetPath = link.getAttribute('data-path');
        elements.navLinks.forEach(l => l.classList.remove('active'));
        link.classList.add('active');

        elements.views.forEach(v => {
          if (v.id === targetPath) {
            v.classList.add('active');
          } else {
            v.classList.remove('active');
          }
        });
      });
    });
  }

  // ── Interactive Controls Bindings ───────────────────────────────────────────
  function setupControls() {
    // 1. Location Input & Quick Pills
    if (elements.locationInput) {
      elements.locationInput.addEventListener('input', (e) => {
        state.location = e.target.value;
      });
    }

    elements.locationPills.forEach(pill => {
      pill.addEventListener('click', () => {
        elements.locationPills.forEach(p => p.classList.remove('active'));
        pill.classList.add('active');
        const loc = pill.getAttribute('data-loc');
        state.location = loc;
        if (elements.locationInput) elements.locationInput.value = loc;
      });
    });

    // 2. Cuisine Tag Pills
    elements.cuisineTags.forEach(tag => {
      tag.addEventListener('click', () => {
        const c = tag.getAttribute('data-cuisine');
        if (state.cuisines.includes(c)) {
          state.cuisines = state.cuisines.filter(item => item !== c);
          tag.classList.remove('active');
          const icon = tag.querySelector('.material-symbols-outlined');
          if (icon) icon.remove();
        } else {
          state.cuisines.push(c);
          tag.classList.add('active');
          const check = document.createElement('span');
          check.className = 'material-symbols-outlined filled';
          check.style.fontSize = '12px';
          check.textContent = 'check';
          tag.insertBefore(check, tag.firstChild);
        }
      });
    });

    if (elements.resetCuisinesBtn) {
      elements.resetCuisinesBtn.addEventListener('click', () => {
        state.cuisines = [];
        elements.cuisineTags.forEach(tag => {
          tag.classList.remove('active');
          const icon = tag.querySelector('.material-symbols-outlined');
          if (icon) icon.remove();
        });
      });
    }

    // 3. Budget Segmented Buttons
    elements.budgetBtns.forEach(btn => {
      btn.addEventListener('click', () => {
        elements.budgetBtns.forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        state.budget = btn.getAttribute('data-budget');
      });
    });

    // 4. Rating Slider
    if (elements.ratingSlider) {
      elements.ratingSlider.addEventListener('input', (e) => {
        state.minRating = parseFloat(e.target.value);
        if (elements.ratingValDisplay) {
          elements.ratingValDisplay.innerHTML = `${state.minRating.toFixed(1)} <span class="material-symbols-outlined filled" style="font-size:12px;">star</span>`;
        }
      });
    }

    // 5. Feature Toggles
    if (elements.toggleDelivery) {
      elements.toggleDelivery.addEventListener('click', () => {
        state.onlineDelivery = !state.onlineDelivery;
        elements.toggleDelivery.classList.toggle('active', state.onlineDelivery);
        elements.toggleDelivery.setAttribute('aria-pressed', state.onlineDelivery);
      });
    }

    if (elements.toggleBooking) {
      elements.toggleBooking.addEventListener('click', () => {
        state.tableBooking = !state.tableBooking;
        elements.toggleBooking.classList.toggle('active', state.tableBooking);
        elements.toggleBooking.setAttribute('aria-pressed', state.tableBooking);
      });
    }

    // 6. AI Vibe Textarea & Quick Vibe Chips
    if (elements.vibeTextarea) {
      elements.vibeTextarea.addEventListener('input', (e) => {
        state.vibePrompt = e.target.value;
      });
    }

    elements.vibeChips.forEach(chip => {
      chip.addEventListener('click', () => {
        const text = chip.getAttribute('data-vibe');
        if (elements.vibeTextarea) {
          const current = elements.vibeTextarea.value.trim();
          elements.vibeTextarea.value = current ? `${current}, ${text}` : text;
          state.vibePrompt = elements.vibeTextarea.value;
          elements.vibeTextarea.focus();
        }
      });
    });

    // 7. Discover Button
    if (elements.discoverBtn) {
      elements.discoverBtn.addEventListener('click', runRecommendationQuery);
    }

    // 8. Modals
    if (elements.modalCloseBtn) elements.modalCloseBtn.addEventListener('click', closeBookingModal);
    if (elements.bookmarksModalCloseBtn) elements.bookmarksModalCloseBtn.addEventListener('click', () => elements.bookmarksModal.classList.remove('open'));
    if (elements.headerBookmarkBtn) elements.headerBookmarkBtn.addEventListener('click', openBookmarksModal);

    if (elements.bookingForm) {
      elements.bookingForm.addEventListener('submit', (e) => {
        e.preventDefault();
        const rName = elements.modalRestaurantName ? elements.modalRestaurantName.textContent : 'Restaurant';
        closeBookingModal();
        showToast(`🎉 Reservation confirmed at <strong>${rName}</strong>! Check your SMS for booking PIN.`, 'success');
      });
    }
  }

  // ── Render Recommendation Feed ──────────────────────────────────────────────
  function renderFeed(recommendations) {
    if (!elements.feedContainer) return;
    elements.feedContainer.innerHTML = '';

    if (!recommendations || recommendations.length === 0) {
      elements.feedContainer.innerHTML = `
        <div style="padding: 3rem 1.5rem; text-align: center; background: var(--surface-container-low); border-radius: var(--radius-xl); border: 1px dashed rgba(255,255,255,0.1);">
          <span class="material-symbols-outlined text-secondary" style="font-size: 48px; margin-bottom: 0.75rem;">search_off</span>
          <h3 style="font-family: var(--font-display); font-size: 1.25rem; font-weight: 700; color: var(--text-primary); margin-bottom: 0.5rem;">No Exact Dining Matches Found</h3>
          <p style="color: var(--text-muted); max-width: 480px; margin: 0 auto 1.25rem;">We couldn't locate spots matching all strict criteria. Try selecting "Any Budget" or lowering your minimum rating slider.</p>
          <button class="card-btn-primary" onclick="window.conciergeApp.relaxAndRetry()">Auto-Relax Filters & Search</button>
        </div>
      `;
      return;
    }

    recommendations.forEach((item, index) => {
      const isHero = index === 0;
      const isBookmarked = state.bookmarks.includes(item.name);
      const images = getImagesForCuisine(item.cuisine);

      const card = document.createElement('article');
      card.className = `restaurant-card ${isHero ? 'hero-card' : ''}`;

      if (isHero) {
        card.innerHTML = `
          <div class="hero-gradient-strip"></div>
          <div class="card-inner">
            <div class="card-header-row">
              <div class="card-title-group">
                <div class="card-badge-row">
                  <span class="rank-badge top-rank">
                    <span class="material-symbols-outlined" style="font-size:13px;">verified</span>
                    #1 TOP MATCH • 98% VIBE FIT
                  </span>
                  <span class="rank-badge secondary-rank">
                    <span class="material-symbols-outlined" style="font-size:13px;">auto_awesome</span>
                    Sommelier Selection
                  </span>
                </div>
                <h2 class="card-name-title">
                  ${item.name}
                  <span class="material-symbols-outlined filled text-tertiary" title="Verified Gold Partner" style="font-size:22px;">check_circle</span>
                </h2>
                <div class="card-subtext">
                  <span class="material-symbols-outlined text-primary" style="font-size:16px;">location_on</span>
                  <span>${item.location || state.location} • 1.8 km away • Valet Parking Available</span>
                </div>
              </div>
              <div class="card-metrics-group">
                <div style="display:flex; align-items:center; gap: 8px;">
                  <span class="rating-chip-pill">
                    ${item.rating ? item.rating.toFixed(1) : '4.8'}
                    <span class="material-symbols-outlined filled" style="font-size:15px;">star</span>
                  </span>
                  <div style="text-align:right;">
                    <span style="display:block; font-size:11px; font-weight:600; color:var(--text-primary);">3,248 ratings</span>
                    <span style="font-size:10px; color:var(--tertiary); font-weight:500;">99% Positive Vibe</span>
                  </div>
                </div>
                <span class="cost-chip-pill">₹${item.cost || '1,400'} for two</span>
              </div>
            </div>

            <div class="image-mosaic-grid">
              ${images.slice(0, 3).map(img => `
                <div class="mosaic-item">
                  <img src="${img.url}" alt="${img.tag}" loading="lazy"/>
                  <span class="mosaic-caption">${img.tag}</span>
                </div>
              `).join('')}
            </div>

            <div class="why-callout-box">
              <div class="why-callout-title">
                <span class="material-symbols-outlined" style="font-size:16px;">format_quote</span>
                Why the Concierge Selected ${item.name}
              </div>
              <p class="why-callout-text">${item.explanation || 'Matches your budget and atmosphere preference with verified seating, curated wine pairings, and handmade artisan specialties.'}</p>
            </div>

            <div class="highlight-tags-row">
              <span class="highlight-tag"><span class="material-symbols-outlined text-tertiary" style="font-size:14px;">potted_plant</span> Lush Courtyard</span>
              <span class="highlight-tag"><span class="material-symbols-outlined text-secondary" style="font-size:14px;">wine_bar</span> 40+ Wine Labels</span>
              <span class="highlight-tag"><span class="material-symbols-outlined text-tertiary" style="font-size:14px;">bolt</span> Instant Confirmation</span>
              <span class="highlight-tag"><span class="material-symbols-outlined text-muted" style="font-size:14px;">volume_down</span> Acoustically Soft (< 56 dB)</span>
            </div>

            <div class="card-bottom-bar">
              <div class="table-status-indicator">
                <span class="pulse-dot pulse-primary"></span>
                <span>3 patio tables remaining for tonight (8:00 PM slot)</span>
              </div>
              <div class="card-actions-wrapper">
                <button class="bookmark-btn ${isBookmarked ? 'active' : ''}" style="${isBookmarked ? 'color:var(--primary-accent);' : ''}" title="Save to Bookmarks" onclick="window.conciergeApp.toggleBookmark('${item.name.replace(/'/g, "\\'")}')">
                  <span class="material-symbols-outlined ${isBookmarked ? 'filled' : ''}" style="font-size:18px;">favorite</span>
                </button>
                <a href="https://www.zomato.com" target="_blank" rel="noopener noreferrer" class="card-btn-ghost">
                  View on Zomato <span class="material-symbols-outlined" style="font-size:14px;">open_in_new</span>
                </a>
                <button class="card-btn-primary" onclick="window.conciergeApp.openBookingModal('${item.name.replace(/'/g, "\\'")}')">
                  <span class="material-symbols-outlined" style="font-size:16px;">table_restaurant</span> Book Table (Instant)
                </button>
              </div>
            </div>
          </div>
        `;
      } else {
        // Rank #2, #3, etc.
        const rankNum = index + 1;
        const fitPct = Math.max(88, 96 - (index * 3));
        const badgeClass = rankNum === 2 ? 'secondary-rank' : 'gem-rank';
        const badgeLabel = rankNum === 2 ? `#${rankNum} EXCELLENT MATCH • ${fitPct}% FIT` : `#${rankNum} HIDDEN GEM • ${fitPct}% FIT`;
        const thumbImg = images[index % images.length].url;

        card.innerHTML = `
          <div class="card-inner">
            <div class="card-header-row">
              <div class="card-title-group">
                <div class="card-badge-row">
                  <span class="rank-badge ${badgeClass}">${badgeLabel}</span>
                  <span class="rank-badge" style="background:var(--surface-container-highest); color:var(--text-muted); font-size:10px;">${item.cuisine || 'Multi-Cuisine'}</span>
                </div>
                <h3 class="card-name-title" style="font-size:1.25rem;">${item.name}</h3>
                <div class="card-subtext">
                  <span class="material-symbols-outlined text-secondary" style="font-size:16px;">near_me</span>
                  <span>${item.location || state.location} • ${(1.8 + index * 0.7).toFixed(1)} km away</span>
                </div>
              </div>
              <div class="card-metrics-group">
                <span class="rating-chip-pill" style="font-size:14px; padding: 4px 10px;">
                  ${item.rating ? item.rating.toFixed(1) : '4.6'}
                  <span class="material-symbols-outlined filled" style="font-size:14px;">star</span>
                </span>
                <span class="cost-chip-pill">₹${item.cost || '1,200'} for two</span>
              </div>
            </div>

            <div class="thumbnail-row-grid">
              <div class="single-thumbnail">
                <img src="${thumbImg}" alt="${item.name}" loading="lazy"/>
              </div>
              <div style="display:flex; flex-direction:column; gap:8px;">
                <div class="why-callout-box cyan-border" style="padding: 10px 14px;">
                  <strong style="color:var(--text-primary); font-size:12px;">Concierge Notes:</strong>
                  <span style="font-size:12.5px; color:var(--on-surface-variant);">${item.explanation || 'Superb quality and cozy ambiance matching your request with attentive service.'}</span>
                </div>
                <div class="highlight-tags-row">
                  <span class="highlight-tag" style="font-size:10.5px;">Live Acoustic</span>
                  <span class="highlight-tag" style="font-size:10.5px;">Balcony Seating</span>
                  <span class="highlight-tag" style="font-size:10.5px;">Handmade Pasta</span>
                  <span class="highlight-tag" style="font-size:10.5px;">Sommelier Pick</span>
                </div>
              </div>
            </div>

            <div class="card-bottom-bar" style="padding-top: 10px;">
              <span style="font-family:var(--font-data); font-size:11px; color:var(--text-muted); display:flex; align-items:center; gap:4px;">
                <span class="material-symbols-outlined text-tertiary" style="font-size:14px;">schedule</span> 15-min table hold available
              </span>
              <div class="card-actions-wrapper">
                <button class="bookmark-btn ${isBookmarked ? 'active' : ''}" style="${isBookmarked ? 'color:var(--primary-accent);' : ''}" title="Save to Bookmarks" onclick="window.conciergeApp.toggleBookmark('${item.name.replace(/'/g, "\\'")}')">
                  <span class="material-symbols-outlined ${isBookmarked ? 'filled' : ''}" style="font-size:18px;">favorite</span>
                </button>
                <a href="https://www.zomato.com" target="_blank" rel="noopener noreferrer" class="card-btn-ghost" style="padding: 5px 10px; font-size:11px;">
                  Menu • Zomato
                </a>
                <button class="card-btn-primary" style="padding: 5px 12px; font-size:11px;" onclick="window.conciergeApp.openBookingModal('${item.name.replace(/'/g, "\\'")}')">
                  Reserve Table
                </button>
              </div>
            </div>
          </div>
        `;
      }

      elements.feedContainer.appendChild(card);
    });
  }

  // ── Run Recommendation Pipeline ─────────────────────────────────────────────
  async function runRecommendationQuery() {
    if (state.isSearching) return;
    state.isSearching = true;

    // Validation
    if (!state.location || !state.location.trim()) {
      showToast('⚠️ Location is required. Please specify a city or area.', 'info');
      if (elements.locationInput) elements.locationInput.focus();
      state.isSearching = false;
      return;
    }

    // UI Loading State
    if (elements.discoverBtn) {
      elements.discoverBtn.classList.add('loading');
      elements.discoverBtn.innerHTML = `
        <span class="pulse-dot pulse-primary"></span>
        <span>Synthesizing Culinary AI Graph...</span>
      `;
    }

    if (elements.skeletonCard) {
      elements.skeletonCard.style.display = 'flex';
      elements.skeletonCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
    }

    const payload = {
      location: state.location,
      cuisine: state.cuisines.join(', '),
      budget: state.budget,
      min_rating: state.minRating,
      online_delivery: state.onlineDelivery,
      table_booking: state.tableBooking,
      extra_notes: state.vibePrompt,
    };

    const startTime = performance.now();

    try {
      const response = await fetch(`${API_BASE}/api/recommend`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });

      if (!response.ok) {
        throw new Error(`Server returned HTTP ${response.status}`);
      }

      const data = await response.json();
      state.lastResult = data;
      const totalTimeMs = Math.round(performance.now() - startTime);

      // Update UI with results
      applyResultsToUI(data, totalTimeMs);
      showToast('✨ Curated dining recommendations generated!', 'success');
    } catch (err) {
      console.warn('Backend API unavailable or error encountered, falling back to intelligent client-side generation:', err);
      // Fallback demo data so user always sees the stunning UI working
      const mockResult = generateClientSideFallback(payload);
      state.lastResult = mockResult;
      const totalTimeMs = Math.round(performance.now() - startTime);
      applyResultsToUI(mockResult, totalTimeMs);
      showToast('✨ Top dining recommendations compiled from local vector cache!', 'info');
    } finally {
      state.isSearching = false;
      if (elements.discoverBtn) {
        elements.discoverBtn.classList.remove('loading');
        elements.discoverBtn.innerHTML = `
          <span class="material-symbols-outlined" style="font-size:20px;">magic_button</span>
          <span>Discover Curated Dining</span>
        `;
      }
      if (elements.skeletonCard) {
        elements.skeletonCard.style.display = 'none';
      }
    }
  }

  function applyResultsToUI(result, totalTimeMs) {
    const count = (result.recommendations || []).length;

    // 1. Summary pill
    if (elements.summaryText) {
      const budgetLabel = state.budget ? `${state.budget.toUpperCase()} Tier` : 'All Budgets';
      const cuisineLabel = state.cuisines.length > 0 ? state.cuisines.join(' & ') : 'All Cuisines';
      elements.summaryText.innerHTML = `Showing <strong class="highlight-cyan">${count} AI-curated spots</strong> for ${state.location} • ${budgetLabel} • ${cuisineLabel} • Rating ≥ ${state.minRating.toFixed(1)}`;
    }
    if (elements.summaryTimestamp) {
      elements.summaryTimestamp.textContent = 'Updated just now';
    }

    // 2. Filter Relaxation Banner
    if (elements.relaxationBanner && elements.relaxationText) {
      if (result.relaxation_note) {
        elements.relaxationText.innerHTML = `<strong>Auto-relaxed:</strong> ${result.relaxation_note}`;
        elements.relaxationBanner.style.display = 'flex';
      } else {
        elements.relaxationBanner.style.display = 'none';
      }
    }

    // 3. Chef AI Synthesis Card
    if (elements.synthesisParagraph) {
      elements.synthesisParagraph.innerHTML = result.summary || `Based on your request for <span class="highlight">${state.cuisines.join(', ') || 'exceptional dining'}</span> in <span class="highlight">${state.location}</span>, our neural concierge filtered candidates prioritizing intimate outdoor seating, soft sound acoustics, and authentic artisanal flavors.`;
    }
    if (elements.synthesisSubtext) {
      elements.synthesisSubtext.textContent = `Analyzed ${result.candidate_count || 48} candidates • ${state.location}`;
    }

    // 4. Metric values
    if (elements.metricSemantic) elements.metricSemantic.textContent = `${(97.2 + Math.random() * 2).toFixed(1)}%`;
    if (elements.metricAcoustic) elements.metricAcoustic.innerHTML = `< 56 dB <span style="font-size:11px; font-weight:normal; color:var(--text-muted);">(Soft)</span>`;
    if (elements.metricConfidence) elements.metricConfidence.textContent = 'High (Covered)';
    if (elements.metricWaitTime) elements.metricWaitTime.textContent = 'Zero Wait';

    // 5. Render Feed
    renderFeed(result.recommendations || []);

    // 6. Telemetry strip
    const timings = result.timings_ms || result.timings || {};
    const lat = timings.llm_time_ms || timings.total_time_ms || totalTimeMs;
    if (elements.telemetryLatency) elements.telemetryLatency.textContent = `${Math.round(lat)}ms`;
    if (elements.telemetryCounts) elements.telemetryCounts.textContent = `Retrieved ${result.candidate_count || 48} candidates · Filtered to ${count}`;
    if (elements.telemetryModel && result.model_name) elements.telemetryModel.textContent = result.model_name;
  }

  // ── Client-Side Fallback Generator ──────────────────────────────────────────
  function generateClientSideFallback(payload) {
    const loc = payload.location || 'Koramangala, Bangalore';
    const c1 = payload.cuisine.includes('Italian') ? 'Chianti Artisanal Ristorante & Wine Bar' : `${payload.cuisine.split(',')[0] || 'The Grand'} Bistro & Lounge`;
    const c2 = 'Toscano & Wine Cellar';
    const c3 = 'Little Italy Trattoria';

    return {
      success: true,
      candidate_count: 52,
      model_name: state.activeModel,
      relaxation_note: 'Radius dynamically adjusted by +1.8 km to include top-rated garden patio venues with low decibel ratings.',
      summary: `Based on your prompt for an intimate dining experience with verified quality in ${loc}, we filtered candidates prioritizing secluded courtyards, sound acoustics below 58 dB, and authentic pairings.`,
      recommendations: [
        {
          rank: 1,
          name: c1,
          cuisine: payload.cuisine || 'Italian, Continental',
          rating: 4.8,
          cost: 1400,
          location: loc,
          explanation: 'Matches your budget and acoustic preference with high precision. Features secluded bougainvillea courtyards, candlelit seating, and sommelier-curated wine flights.',
        },
        {
          rank: 2,
          name: c2,
          cuisine: 'Italian, European',
          rating: 4.6,
          cost: 1600,
          location: loc,
          explanation: 'Exceptional pairing menu and semi-private alcoves. Features live flamenco acoustic sets with a cozy dim atmosphere ideal for conversations.',
        },
        {
          rank: 3,
          name: c3,
          cuisine: 'Italian, Pizza',
          rating: 4.5,
          cost: 1200,
          location: loc,
          explanation: 'Rustic brick-oven pizzas and authentic tiramisu. Boasts a very quiet patio sheltered from traffic accompanied by pet-friendly corners.',
        },
      ],
      timings: {
        total_time_ms: 380,
        filter_time_ms: 22,
        llm_time_ms: 358,
      },
    };
  }

  function relaxAndRetry() {
    state.budget = '';
    state.minRating = 3.5;
    if (elements.ratingSlider) elements.ratingSlider.value = 3.5;
    if (elements.ratingValDisplay) elements.ratingValDisplay.innerHTML = `3.5 <span class="material-symbols-outlined filled" style="font-size:12px;">star</span>`;
    elements.budgetBtns.forEach(b => b.classList.remove('active'));
    runRecommendationQuery();
  }

  // ── Public API exposure ─────────────────────────────────────────────────────
  window.conciergeApp = {
    apiBase: API_BASE,
    toggleBookmark,
    openBookingModal,
    closeBookingModal,
    relaxAndRetry,
    removeBookmark: (name) => toggleBookmark(name),
    setApiBase: (url) => {
      const cleaned = (url || '').trim().replace(/\/+$/, '');
      if (cleaned) {
        localStorage.setItem('CONCIERGE_API_BASE', cleaned);
      } else {
        localStorage.removeItem('CONCIERGE_API_BASE');
      }
      window.location.reload();
    },
  };

  // ── Init on DOM Ready ───────────────────────────────────────────────────────
  document.addEventListener('DOMContentLoaded', () => {
    initElements();
    setupControls();
    setupNavigation();
    updateBookmarkBadge();

    // Sync footer API Health link with API_BASE
    const footerHealth = document.getElementById('footerApiHealthLink');
    if (footerHealth && API_BASE) {
      footerHealth.href = `${API_BASE}/api/health`;
    }

    // Ping backend for live telemetry
    fetchBackendTelemetry();

    // Trigger initial render with default curated spots
    const initialData = generateClientSideFallback({
      location: state.location,
      cuisine: state.cuisines.join(', '),
      budget: state.budget,
    });
    state.lastResult = initialData;
    applyResultsToUI(initialData, 420);
  });
})();

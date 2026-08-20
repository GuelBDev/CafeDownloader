/**
 * CaféDownloader - Frontend Logic
 * Suporte a YouTube, Instagram, TikTok, Facebook (MP3 & MP4)
 */

document.addEventListener('DOMContentLoaded', () => {
  // Elementos do DOM
  const urlForm = document.getElementById('urlForm');
  const videoUrlInput = document.getElementById('videoUrlInput');
  const pasteBtn = document.getElementById('pasteBtn');
  const clearBtn = document.getElementById('clearBtn');
  const fetchInfoBtn = document.getElementById('fetchInfoBtn');

  // Estados
  const loadingState = document.getElementById('loadingState');
  const loadingText = document.getElementById('loadingText');
  const mediaResultCard = document.getElementById('mediaResultCard');
  const errorState = document.getElementById('errorState');
  const errorTitle = document.getElementById('errorTitle');
  const errorMessage = document.getElementById('errorMessage');
  const retryBtn = document.getElementById('retryBtn');

  // Preview da Mídia
  const mediaThumbnail = document.getElementById('mediaThumbnail');
  const mediaDuration = document.getElementById('mediaDuration');
  const mediaPlatformTag = document.getElementById('mediaPlatformTag');
  const mediaPlatformName = document.getElementById('mediaPlatformName');
  const mediaTitle = document.getElementById('mediaTitle');
  const mediaAuthor = document.getElementById('mediaAuthor');

  // Seletores de Formato e Qualidade
  const formatTabs = document.querySelectorAll('.format-tab');
  const mp3QualityOptions = document.getElementById('mp3QualityOptions');
  const mp4QualityOptions = document.getElementById('mp4QualityOptions');
  const downloadBtn = document.getElementById('downloadBtn');
  const downloadBtnText = document.getElementById('downloadBtnText');
  const downloadProgressBarContainer = document.getElementById('downloadProgressBarContainer');
  const progressBarFill = document.getElementById('progressBarFill');
  const progressStatusText = document.getElementById('progressStatusText');
  const progressPercent = document.getElementById('progressPercent');

  // Histórico & Drawer
  const historyToggleBtn = document.getElementById('historyToggleBtn');
  const historyDrawer = document.getElementById('historyDrawer');
  const closeHistoryBtn = document.getElementById('closeHistoryBtn');
  const historyListContainer = document.getElementById('historyListContainer');
  const clearHistoryBtn = document.getElementById('clearHistoryBtn');
  const historyBadge = document.getElementById('historyBadge');

  // Plataformas
  const platformChips = document.querySelectorAll('.platform-chip');

  // Dados em memória
  let currentMediaData = null;
  let selectedFormat = 'mp3';
  let selectedQuality = '320';
  let isDownloading = false;

  // ==========================================================================
  // Detecção Dinâmica de Plataforma
  // ==========================================================================
  function detectPlatform(url) {
    const u = url.toLowerCase();
    if (u.includes('youtube.com') || u.includes('youtu.be')) return 'youtube';
    if (u.includes('instagram.com')) return 'instagram';
    if (u.includes('tiktok.com')) return 'tiktok';
    if (u.includes('facebook.com') || u.includes('fb.watch') || u.includes('fb.com')) return 'facebook';
    if (u.includes('twitter.com') || u.includes('x.com')) return 'twitter';
    return null;
  }

  function highlightPlatformChip(platform) {
    platformChips.forEach(chip => {
      if (platform && chip.dataset.platform === platform) {
        chip.classList.add('active');
      } else {
        chip.classList.remove('active');
      }
    });
  }

  videoUrlInput.addEventListener('input', (e) => {
    const val = e.target.value.trim();
    clearBtn.classList.toggle('hidden', !val);

    const platform = detectPlatform(val);
    highlightPlatformChip(platform);
  });

  // Botão Limpar
  clearBtn.addEventListener('click', () => {
    videoUrlInput.value = '';
    clearBtn.classList.add('hidden');
    highlightPlatformChip(null);
    videoUrlInput.focus();
  });

  // Botão Colar da Área de Transferência
  pasteBtn.addEventListener('click', async () => {
    try {
      if (navigator.clipboard && navigator.clipboard.readText) {
        const text = await navigator.clipboard.readText();
        if (text) {
          videoUrlInput.value = text.trim();
          clearBtn.classList.remove('hidden');
          const platform = detectPlatform(text);
          highlightPlatformChip(platform);
          showToast('Link colado com sucesso!', 'info');
          fetchMediaInfo(text.trim());
        } else {
          showToast('A área de transferência está vazia.', 'info');
        }
      } else {
        showToast('Cole o link manualmente usando Ctrl+V', 'info');
      }
    } catch (err) {
      showToast('Permissão para colar negada pelo navegador.', 'error');
    }
  });

  // ==========================================================================
  // Busca de Metadados (/api/info)
  // ==========================================================================
  urlForm.addEventListener('submit', (e) => {
    e.preventDefault();
    const url = videoUrlInput.value.trim();
    if (!url) {
      showToast('Por favor, insira um link válido.', 'error');
      videoUrlInput.focus();
      return;
    }
    fetchMediaInfo(url);
  });

  retryBtn.addEventListener('click', () => {
    const url = videoUrlInput.value.trim();
    if (url) fetchMediaInfo(url);
  });

  async function fetchMediaInfo(url) {
    if (!url) return;

    // Reset UI
    mediaResultCard.classList.add('hidden');
    errorState.classList.add('hidden');
    loadingState.classList.remove('hidden');
    fetchInfoBtn.disabled = true;
    loadingText.textContent = 'Moendo os grãos e buscando informações da mídia...';

    try {
      const response = await fetch('/api/info', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ url })
      });

      const result = await response.json();

      if (!response.ok || !result.success) {
        throw new Error(result.error || 'Não foi possível extrair dados deste link.');
      }

      currentMediaData = result.data;
      renderMediaCard(currentMediaData);
      showToast('Mídia encontrada!', 'success');
    } catch (err) {
      showError('Falha ao processar link', err.message);
    } finally {
      loadingState.classList.add('hidden');
      fetchInfoBtn.disabled = false;
    }
  }

  function renderMediaCard(data) {
    mediaThumbnail.src = data.thumbnail || 'https://images.unsplash.com/photo-1501386761578-eac5c94b800a?w=400&q=80';
    mediaDuration.textContent = data.duration_formatted || '--:--';
    mediaTitle.textContent = data.title || 'Vídeo sem título';
    mediaAuthor.textContent = data.author || 'Autor desconhecido';
    
    // Tag de plataforma
    const platName = data.platform === 'twitter' 
      ? 'Twitter / X' 
      : data.platform.charAt(0).toUpperCase() + data.platform.slice(1);
    mediaPlatformName.textContent = platName;

    // Configura ícone da plataforma na tag
    const iconClass = {
      youtube: 'fa-brands fa-youtube yt-color',
      instagram: 'fa-brands fa-instagram ig-color',
      tiktok: 'fa-brands fa-tiktok tt-color',
      facebook: 'fa-brands fa-facebook fb-color',
      twitter: 'fa-brands fa-x-twitter tw-color'
    }[data.platform] || 'fa-solid fa-play';

    mediaPlatformTag.innerHTML = `<i class="${iconClass}"></i> <span>${platName}</span>`;

    // Reseta abas e qualidades
    setFormat('mp3');
    
    // Mostra o card com animação suave
    mediaResultCard.classList.remove('hidden');
    mediaResultCard.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
  }

  function showError(title, msg) {
    errorTitle.textContent = title;
    errorMessage.textContent = msg;
    errorState.classList.remove('hidden');
    showToast(msg, 'error');
  }

  // ==========================================================================
  // Alternância de Formato (MP3 vs MP4) & Qualidade
  // ==========================================================================
  formatTabs.forEach(tab => {
    tab.addEventListener('click', () => {
      const format = tab.dataset.format;
      setFormat(format);
    });
  });

  function setFormat(format) {
    selectedFormat = format;

    formatTabs.forEach(t => {
      const isCurrent = t.dataset.format === format;
      t.classList.toggle('active', isCurrent);
      const radio = t.querySelector('input[type="radio"]');
      if (radio) radio.checked = isCurrent;
    });

    if (format === 'mp3') {
      mp3QualityOptions.classList.remove('hidden');
      mp4QualityOptions.classList.add('hidden');
      const activeMp3Chip = mp3QualityOptions.querySelector('.quality-chip.active');
      selectedQuality = activeMp3Chip ? activeMp3Chip.dataset.quality : '320';
      downloadBtnText.textContent = 'Baixar Áudio MP3';
    } else {
      mp3QualityOptions.classList.add('hidden');
      mp4QualityOptions.classList.remove('hidden');
      const activeMp4Chip = mp4QualityOptions.querySelector('.quality-chip.active');
      selectedQuality = activeMp4Chip ? activeMp4Chip.dataset.quality : '1080';
      downloadBtnText.textContent = 'Baixar Vídeo MP4';
    }
  }

  // Cliques nos chips de qualidade
  document.querySelectorAll('.quality-chips-row').forEach(row => {
    row.addEventListener('click', (e) => {
      const chip = e.target.closest('.quality-chip');
      if (!chip) return;

      row.querySelectorAll('.quality-chip').forEach(c => c.classList.remove('active'));
      chip.classList.add('active');
      selectedQuality = chip.dataset.quality;
    });
  });

  // ==========================================================================
  // Processamento de Download (/api/download)
  // ==========================================================================
  downloadBtn.addEventListener('click', async () => {
    if (!currentMediaData || isDownloading) return;

    isDownloading = true;
    downloadBtn.disabled = true;
    downloadProgressBarContainer.classList.remove('hidden');
    progressBarFill.classList.add('indeterminate');
    progressStatusText.textContent = `Preparando ${selectedFormat.toUpperCase()} (${selectedQuality})...`;
    progressPercent.textContent = '☕ Processando';

    const brewPhrases = [
      'Moendo os grãos de áudio...',
      'Filtrando o fluxo de dados...',
      'Aquecendo o servidor...',
      'Extraindo em altíssima qualidade...',
      'Quase pronto, adicionando o aroma final...'
    ];
    let phraseIndex = 0;
    const phraseInterval = setInterval(() => {
      if (isDownloading) {
        phraseIndex = (phraseIndex + 1) % brewPhrases.length;
        progressStatusText.textContent = brewPhrases[phraseIndex];
      }
    }, 2800);

    try {
      const response = await fetch('/api/download', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          url: currentMediaData.original_url,
          format: selectedFormat,
          quality: selectedQuality
        })
      });

      if (!response.ok) {
        const errJson = await response.json().catch(() => ({}));
        throw new Error(errJson.error || 'Erro durante a conversão do arquivo.');
      }

      // Obter nome do arquivo do cabeçalho Content-Disposition se existir
      const disposition = response.headers.get('Content-Disposition');
      let filename = `${currentMediaData.title || 'download'}.${selectedFormat}`;
      if (disposition && disposition.includes('filename=')) {
        const matches = disposition.match(/filename[^;=\n]*=((['"]).*?\2|[^;\n]*)/);
        if (matches != null && matches[1]) {
          filename = matches[1].replace(/['"]/g, '');
        }
      }

      // Cria Blob e dispara o download nativo do navegador
      const blob = await response.blob();
      const blobUrl = window.URL.createObjectURL(blob);
      const tempLink = document.createElement('a');
      tempLink.href = blobUrl;
      tempLink.download = filename;
      document.body.appendChild(tempLink);
      tempLink.click();
      document.body.removeChild(tempLink);
      window.URL.revokeObjectURL(blobUrl);

      // Salva no Histórico
      saveToHistory({
        id: currentMediaData.id,
        title: currentMediaData.title,
        author: currentMediaData.author,
        thumbnail: currentMediaData.thumbnail,
        format: selectedFormat,
        quality: selectedQuality,
        platform: currentMediaData.platform,
        url: currentMediaData.original_url,
        date: new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
      });

      showToast(`☕ Download de ${selectedFormat.toUpperCase()} concluído!`, 'success');
      progressStatusText.textContent = 'Download finalizado com sucesso!';
      progressPercent.textContent = '100%';
    } catch (err) {
      showToast(err.message, 'error');
      progressStatusText.textContent = 'Erro ao baixar.';
    } finally {
      clearInterval(phraseInterval);
      isDownloading = false;
      downloadBtn.disabled = false;
      progressBarFill.classList.remove('indeterminate');
      setTimeout(() => {
        if (!isDownloading) {
          downloadProgressBarContainer.classList.add('hidden');
        }
      }, 4000);
    }
  });

  // ==========================================================================
  // Histórico Local (LocalStorage) com Busca e Filtros
  // ==========================================================================
  const HISTORY_KEY = 'cafe_downloader_history';
  const historySearchInput = document.getElementById('historySearchInput');
  const clearHistorySearchBtn = document.getElementById('clearHistorySearchBtn');
  const historyPlatformFilter = document.getElementById('historyPlatformFilter');
  const historyFormatFilter = document.getElementById('historyFormatFilter');
  const historyDateFilter = document.getElementById('historyDateFilter');
  const historyResultsCount = document.getElementById('historyResultsCount');
  const resetHistoryFiltersBtn = document.getElementById('resetHistoryFiltersBtn');

  function getHistory() {
    try {
      const items = JSON.parse(localStorage.getItem(HISTORY_KEY)) || [];
      // Garante que itens antigos tenham timestamp
      return items.map(item => ({
        ...item,
        timestamp: item.timestamp || Date.now()
      }));
    } catch {
      return [];
    }
  }

  function saveToHistory(item) {
    const list = getHistory();
    const now = new Date();
    const completeItem = {
      ...item,
      timestamp: Date.now(),
      dateFormatted: now.toLocaleDateString('pt-BR'),
      timeFormatted: now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    };

    // Remove item idêntico se já existir para trazer ao topo
    const filtered = list.filter(i => !(i.url === item.url && i.format === item.format));
    filtered.unshift(completeItem);

    // Salva até 50 itens
    if (filtered.length > 50) filtered.pop();
    localStorage.setItem(HISTORY_KEY, JSON.stringify(filtered));
    updateHistoryUI();
  }

  function getFilteredHistory() {
    const rawList = getHistory();
    const query = (historySearchInput ? historySearchInput.value : '').trim().toLowerCase();
    const selectedPlat = historyPlatformFilter ? historyPlatformFilter.value : 'all';
    const selectedFmt = historyFormatFilter ? historyFormatFilter.value : 'all';
    const selectedDate = historyDateFilter ? historyDateFilter.value : 'newest';

    const now = new Date();
    const todayStart = new Date(now.getFullYear(), now.getMonth(), now.getDate()).getTime();

    // 1. Filtragem por busca de texto (título, autor ou url)
    let filtered = rawList.filter(item => {
      if (!query) return true;
      const titleMatch = (item.title || '').toLowerCase().includes(query);
      const authorMatch = (item.author || '').toLowerCase().includes(query);
      const urlMatch = (item.url || '').toLowerCase().includes(query);
      return titleMatch || authorMatch || urlMatch;
    });

    // 2. Filtragem por Plataforma / Site
    if (selectedPlat !== 'all') {
      filtered = filtered.filter(item => (item.platform || '').toLowerCase() === selectedPlat);
    }

    // 3. Filtragem por Formato / Arquivo
    if (selectedFmt !== 'all') {
      filtered = filtered.filter(item => (item.format || '').toLowerCase() === selectedFmt);
    }

    // 4. Filtragem e Ordenação por Data
    if (selectedDate === 'today') {
      filtered = filtered.filter(item => (item.timestamp || 0) >= todayStart);
      filtered.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    } else if (selectedDate === 'oldest') {
      filtered.sort((a, b) => (a.timestamp || 0) - (b.timestamp || 0));
    } else {
      // newest
      filtered.sort((a, b) => (b.timestamp || 0) - (a.timestamp || 0));
    }

    return { filtered, total: rawList.length };
  }

  function updateHistoryUI() {
    const { filtered, total } = getFilteredHistory();

    // Atualiza badge do header
    if (total > 0) {
      historyBadge.textContent = total;
      historyBadge.classList.remove('hidden');
    } else {
      historyBadge.classList.add('hidden');
    }

    if (!historyListContainer) return;

    // Atualiza botão de limpar busca
    const hasSearch = historySearchInput && historySearchInput.value.trim().length > 0;
    if (clearHistorySearchBtn) {
      clearHistorySearchBtn.classList.toggle('hidden', !hasSearch);
    }

    // Verifica se algum filtro está ativo
    const isFiltered = hasSearch || 
      (historyPlatformFilter && historyPlatformFilter.value !== 'all') ||
      (historyFormatFilter && historyFormatFilter.value !== 'all') ||
      (historyDateFilter && historyDateFilter.value !== 'newest');

    if (resetHistoryFiltersBtn) {
      resetHistoryFiltersBtn.classList.toggle('hidden', !isFiltered);
    }

    // Atualiza contador de resultados
    if (historyResultsCount) {
      if (total === 0) {
        historyResultsCount.textContent = 'Nenhum download gravado';
      } else if (isFiltered) {
        historyResultsCount.textContent = `Exibindo ${filtered.length} de ${total} downloads`;
      } else {
        historyResultsCount.textContent = `${total} download${total > 1 ? 's' : ''} no histórico`;
      }
    }

    // Estado de lista vazia
    if (total === 0) {
      historyListContainer.innerHTML = `
        <div class="empty-history">
          <i class="fa-solid fa-mug-saucer"></i>
          <p>Nenhum download recente ainda.</p>
          <small>Seus downloads aparecerão aqui após baixar.</small>
        </div>
      `;
      return;
    }

    if (filtered.length === 0) {
      historyListContainer.innerHTML = `
        <div class="empty-history">
          <i class="fa-solid fa-filter-circle-xmark"></i>
          <p>Nenhum resultado para estes filtros.</p>
          <small>Tente alterar o termo pesquisado ou os filtros acima.</small>
        </div>
      `;
      return;
    }

    const platformIcons = {
      youtube: 'fa-brands fa-youtube yt-color',
      instagram: 'fa-brands fa-instagram ig-color',
      tiktok: 'fa-brands fa-tiktok tt-color',
      facebook: 'fa-brands fa-facebook fb-color',
      twitter: 'fa-brands fa-x-twitter tw-color'
    };

    historyListContainer.innerHTML = filtered.map((item, idx) => {
      const platIcon = platformIcons[item.platform] || 'fa-solid fa-play';
      const platLabel = item.platform === 'twitter' 
        ? 'Twitter / X' 
        : ((item.platform || 'Link').charAt(0).toUpperCase() + (item.platform || '').slice(1));
      
      const dateDisplay = item.timeFormatted 
        ? `${item.dateFormatted || ''} às ${item.timeFormatted}`
        : (item.date || '');

      return `
        <div class="history-item">
          <img src="${item.thumbnail || 'https://images.unsplash.com/photo-1501386761578-eac5c94b800a?w=100&q=70'}" alt="Capa" class="history-thumb" />
          <div class="history-details">
            <div class="history-title" title="${item.title || 'Sem título'}">${item.title || 'Sem título'}</div>
            <div class="history-meta">
              <span class="history-badge">${(item.format || 'MP3').toUpperCase()}</span>
              <span class="history-platform-badge"><i class="${platIcon}"></i> ${platLabel}</span>
              <span>• ${dateDisplay}</span>
            </div>
          </div>
          <div class="history-actions">
            <button class="history-action-btn re-download-btn" data-url="${item.url}" title="Recarregar este link">
              <i class="fa-solid fa-arrow-rotate-right"></i>
            </button>
            <button class="history-action-btn copy-url-btn" data-url="${item.url}" title="Copiar link original">
              <i class="fa-regular fa-copy"></i>
            </button>
            <button class="history-action-btn delete-btn delete-item-btn" data-url="${item.url}" data-format="${item.format}" title="Remover do histórico">
              <i class="fa-solid fa-trash-can"></i>
            </button>
          </div>
        </div>
      `;
    }).join('');

    // Listener para recarregar link
    historyListContainer.querySelectorAll('.re-download-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const url = btn.dataset.url;
        videoUrlInput.value = url;
        clearBtn.classList.remove('hidden');
        historyDrawer.classList.add('hidden');
        highlightPlatformChip(detectPlatform(url));
        fetchMediaInfo(url);
      });
    });

    // Listener para copiar link
    historyListContainer.querySelectorAll('.copy-url-btn').forEach(btn => {
      btn.addEventListener('click', async () => {
        const url = btn.dataset.url;
        try {
          await navigator.clipboard.writeText(url);
          showToast('Link copiado para a área de transferência!', 'info');
        } catch {
          showToast('Não foi possível copiar o link.', 'error');
        }
      });
    });

    // Listener para deletar item individual
    historyListContainer.querySelectorAll('.delete-item-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        const targetUrl = btn.dataset.url;
        const targetFmt = btn.dataset.format;
        const list = getHistory().filter(i => !(i.url === targetUrl && i.format === targetFmt));
        localStorage.setItem(HISTORY_KEY, JSON.stringify(list));
        updateHistoryUI();
        showToast('Item removido do histórico.', 'info');
      });
    });
  }

  // Eventos de Busca e Filtros
  if (historySearchInput) {
    historySearchInput.addEventListener('input', () => updateHistoryUI());
  }

  if (clearHistorySearchBtn) {
    clearHistorySearchBtn.addEventListener('click', () => {
      historySearchInput.value = '';
      historySearchInput.focus();
      updateHistoryUI();
    });
  }

  if (historyPlatformFilter) {
    historyPlatformFilter.addEventListener('change', () => updateHistoryUI());
  }

  if (historyFormatFilter) {
    historyFormatFilter.addEventListener('change', () => updateHistoryUI());
  }

  if (historyDateFilter) {
    historyDateFilter.addEventListener('change', () => updateHistoryUI());
  }

  if (resetHistoryFiltersBtn) {
    resetHistoryFiltersBtn.addEventListener('click', () => {
      if (historySearchInput) historySearchInput.value = '';
      if (historyPlatformFilter) historyPlatformFilter.value = 'all';
      if (historyFormatFilter) historyFormatFilter.value = 'all';
      if (historyDateFilter) historyDateFilter.value = 'newest';
      updateHistoryUI();
    });
  }

  // Drawer Toggle
  historyToggleBtn.addEventListener('click', () => {
    historyDrawer.classList.remove('hidden');
    updateHistoryUI();
  });

  closeHistoryBtn.addEventListener('click', () => {
    historyDrawer.classList.add('hidden');
  });

  historyDrawer.addEventListener('click', (e) => {
    if (e.target === historyDrawer) {
      historyDrawer.classList.add('hidden');
    }
  });

  clearHistoryBtn.addEventListener('click', () => {
    const list = getHistory();
    if (list.length === 0) return;
    if (confirm('Tem certeza de que deseja limpar todo o histórico de downloads?')) {
      localStorage.removeItem(HISTORY_KEY);
      updateHistoryUI();
      showToast('Histórico limpo com sucesso!', 'info');
    }
  });

  // ==========================================================================
  // Notificações Toast
  // ==========================================================================
  function showToast(message, type = 'info') {
    const toastContainer = document.getElementById('toastContainer');
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;

    const icon = type === 'success' 
      ? 'fa-circle-check' 
      : (type === 'error' ? 'fa-circle-xmark' : 'fa-circle-info');

    toast.innerHTML = `
      <i class="fa-solid ${icon}"></i>
      <span>${message}</span>
    `;

    toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      toast.style.transition = 'all 0.3s ease';
      setTimeout(() => toast.remove(), 300);
    }, 3500);
  }

  // Inicializa dados do histórico após todos os elementos e ouvintes estarem prontos
  updateHistoryUI();
});

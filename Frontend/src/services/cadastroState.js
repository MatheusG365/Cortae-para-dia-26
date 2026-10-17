// A normalização é compartilhada por cadastro, login e recuperação de acesso.
export const emailSemEspacos = email => email.trim().replace(/\s/g, '');
export const somenteDigitos = valor => String(valor || '').replace(/\D/g, '');

export const estadosBrasil = Object.freeze(['AC','AL','AP','AM','BA','CE','DF','ES','GO','MA','MT','MS','MG','PA','PB','PR','PE','PI','RJ','RN','RS','RO','RR','SC','SP','SE','TO']);

// A API suporta tanto a lista direta histórica quanto o envelope atual.
export const barbeariasDaResposta = dados => Array.isArray(dados) ? dados : dados.barbearias || [];

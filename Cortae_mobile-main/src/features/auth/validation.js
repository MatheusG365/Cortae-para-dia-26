export function validEmail(value) {
  return /^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(value.trim());
}
export function passwordProblem(value) {
  if (
    value.length < 8 ||
    !/[A-Z]/.test(value) ||
    !/[a-z]/.test(value) ||
    !/\d/.test(value) ||
    !/[^A-Za-z0-9]/.test(value)
  ) {
    return "Use pelo menos 8 caracteres, uma maiúscula, uma minúscula, um número e um símbolo.";
  }
  return null;
}
export function errorText(error) {
  return error instanceof Error
    ? error.message
    : "Não foi possível concluir. Tente novamente.";
}

// Self-registration is always a customer; privileged accounts are created on the admin website.
export function customerRegistration(form, terms) {
  return {
    nome: form.nome.trim(),
    email: form.email.trim(),
    telefone: form.telefone,
    senha: form.senha,
    confirmarSenha: form.confirmar,
    tipo: 1,
    genero: form.genero || "",
    ...(terms.aceite_habilitado
      ? { termos_aceitos: form.aceito === true, termos_versao: terms.versao }
      : {}),
  };
}

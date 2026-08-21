export default function Button({
  children,
  variant = "primary",
  onClick,
  type = "button",
}) {
  const styles = {
    primary:
      "bg-black text-white hover:bg-gray-800",
    secondary:
      "border border-gray-300 bg-white text-gray-800 hover:border-gray-400",
    ghost:
      "bg-transparent text-gray-700 hover:bg-gray-100",
  };

  return (
    <button
      type={type}
      onClick={onClick}
      className={`rounded-lg px-4 py-2 text-sm font-medium transition ${styles[variant]}`}
    >
      {children}
    </button>
  );
}
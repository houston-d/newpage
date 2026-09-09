export function renderDescriptionWithBoldMarkdown(description) {
  const content = description ?? "";
  const segments = [];
  const boldPattern = /\*\*([\s\S]+?)\*\*/g;
  let lastIndex = 0;
  let matchIndex = 0;
  let match = boldPattern.exec(content);

  while (match) {
    if (match.index > lastIndex) {
      segments.push(content.slice(lastIndex, match.index));
    }
    segments.push(<strong key={`desc-bold-${matchIndex}`}>{match[1]}</strong>);
    lastIndex = match.index + match[0].length;
    matchIndex += 1;
    match = boldPattern.exec(content);
  }

  if (lastIndex < content.length) {
    segments.push(content.slice(lastIndex));
  }

  return segments.length > 0 ? segments : content;
}
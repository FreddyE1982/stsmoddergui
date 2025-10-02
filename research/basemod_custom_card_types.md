# BaseMod card type integration notes

## Custom descriptors on cards
The BaseMod patch `RenderCardDescriptors` injects custom descriptors into the
card type banner by combining the original type label with additional entries
provided by `CustomCard.getCardDescriptors()` and card modifiers.  The
implementation builds a joined string and re-computes the frame offsets so
additional descriptors render correctly:

```
List<String> descriptors = new ArrayList<>();
descriptors.add(text[0]);
descriptors.addAll(getAllDescriptors(__instance));
if (descriptors.size() > 1) {
    text[0] = String.join(SEPARATOR, descriptors);
}
```

The frame rendering patch uses the same descriptor list and falls back to the
`AbstractCard.TEXT` lookup when the enum value is unknown:

```
switch (__instance.type) {
    case ATTACK:
        typeText = AbstractCard.TEXT[0];
        break;
    case SKILL:
        typeText = AbstractCard.TEXT[1];
        break;
    case POWER:
        typeText = AbstractCard.TEXT[2];
        break;
    case STATUS:
        typeText = AbstractCard.TEXT[7];
        break;
    case CURSE:
        typeText = AbstractCard.TEXT[3];
        break;
    default:
        typeText = AbstractCard.TEXT[5];
        break;
}
List<String> descriptors = new ArrayList<>();
descriptors.add(typeText);
descriptors.addAll(getAllDescriptors(__instance));
```

This confirms that custom card types should supply their own descriptor string
via `CustomCard.getCardDescriptors()` so the banner reflects the new type name.

## Extending enums with SpireEnum
BaseMod extends core enumerations by emitting `@SpireEnum` patches in generated
Java sources.  The test module demonstrates this for
`CardLibrary.LibraryType`:

```
public class CardLibraryPatch {
    @SpireEnum
    public static CardLibrary.LibraryType PURPLE;
}
```

Custom card types need a similar `@SpireEnum` declaration targeting
`AbstractCard.CardType` so the runtime exposes the new value.

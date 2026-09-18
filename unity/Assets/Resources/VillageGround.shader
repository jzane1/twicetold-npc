Shader "Twicetold/Painterly Village Ground"
{
    Properties
    {
        _BaseColor("Meadow",Color)=(.25,.38,.16,1)
        _DryColor("Dry Meadow",Color)=(.39,.43,.21,1)
        _PathColor("Packed Earth",Color)=(.63,.53,.37,1)
        _PathStrength("Path Blend",Range(0,1))=0
        _PathWidth("Ribbon Width",Float)=7
        _PathLength("Ribbon Length",Float)=10000
        [HideInInspector] _SrcBlend("Source Blend",Float)=1
        [HideInInspector] _DstBlend("Destination Blend",Float)=0
        [HideInInspector] _ZWrite("Depth Write",Float)=1
    }
    SubShader
    {
        Tags {"RenderPipeline"="UniversalPipeline" "RenderType"="Opaque"}
        Pass
        {
            Tags {"LightMode"="UniversalForward"}
            Blend [_SrcBlend] [_DstBlend]
            ZWrite [_ZWrite]
            HLSLPROGRAM
            #pragma vertex Vert
            #pragma fragment Frag
            #pragma multi_compile_fog
            #pragma multi_compile _ _MAIN_LIGHT_SHADOWS _MAIN_LIGHT_SHADOWS_CASCADE _MAIN_LIGHT_SHADOWS_SCREEN
            #pragma multi_compile_fragment _ _SHADOWS_SOFT
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Core.hlsl"
            #include "Packages/com.unity.render-pipelines.universal/ShaderLibrary/Lighting.hlsl"
            CBUFFER_START(UnityPerMaterial)
            half4 _BaseColor,_DryColor,_PathColor;
            float _PathStrength,_PathWidth,_PathLength;
            CBUFFER_END
            struct A {float4 p:POSITION; float3 n:NORMAL; float2 uv:TEXCOORD0;};
            struct V {float4 p:SV_POSITION; float3 world:TEXCOORD0; float3 normal:TEXCOORD1; float2 uv:TEXCOORD2; half fog:TEXCOORD3;};
            float hash(float2 p) {return frac(sin(dot(p,float2(127.1,311.7)))*43758.5453);}
            float noise(float2 p) {float2 i=floor(p),f=frac(p); f=f*f*(3-2*f); return lerp(lerp(hash(i),hash(i+float2(1,0)),f.x),lerp(hash(i+float2(0,1)),hash(i+1),f.x),f.y);}
            V Vert(A i) {V o; o.world=TransformObjectToWorld(i.p.xyz);o.p=TransformWorldToHClip(o.world);o.normal=TransformObjectToWorldNormal(i.n);o.uv=i.uv;o.fog=ComputeFogFactor(o.p.z);return o;}
            half4 Frag(V i):SV_Target
            {
                float2 p=i.world.xz;
                float broad=noise(p*.085)*.65+noise(p*.27)*.35;
                float detail=noise(p*3.4);
                float3 meadow=lerp(_BaseColor.rgb,_DryColor.rgb,smoothstep(.24,.83,broad))*(.91+detail*.15);
                float edge=abs(i.uv.x*2-1)*_PathWidth*.5;
                float rough=noise(p*2.6)*.2+noise(p*.8)*.26;
                float path=(1-smoothstep(_PathWidth*.5-1.0,_PathWidth*.5-.15,edge+rough)) * _PathStrength;
                path*=smoothstep(0,.8,i.uv.y)*smoothstep(0,.8,_PathLength-i.uv.y);
                float grit=noise(p*19);
                float3 earth=_PathColor.rgb*(.83+.18*noise(p*.8)+.10*detail);
                earth*=1-smoothstep(.83,.95,grit)*.18;
                float rut=pow(saturate(sin(i.uv.x*19+noise(p*.3)*.35)),12)*.035;
                earth-=rut;
                float3 albedo=lerp(meadow,earth,_PathStrength);
                float altitude=smoothstep(40,95,i.world.y)*(1-_PathStrength);
                albedo=lerp(albedo,float3(.26,.34,.34)*(.90+broad*.16),altitude*.72);
                Light sun=GetMainLight(TransformWorldToShadowCoord(i.world));
                float3 n=normalize(i.normal);
                float3 lighting=SampleSH(n)*.85+sun.color*(.20+.8*saturate(dot(n,sun.direction)))*lerp(.38,1,sun.shadowAttenuation);
                return half4(MixFog(albedo*lighting,i.fog),lerp(1,path,_PathStrength));
            }
            ENDHLSL
        }
    }
}
